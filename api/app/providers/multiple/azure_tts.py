import ujson
import time
import httpx
import traceback
import re
from dataclasses import dataclass
from fastapi import Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any, Tuple, Iterable, AsyncGenerator, Optional, Union
from ...responses import PrettyJSONResponse
from ...core import UserManager, ProviderManager, settings
from ...utils import RequestProcessor
from ..ai_models import Model
from ..base_provider import BaseProvider, ProviderConfig
from ..utils import WebhookManager, ErrorHandler

@dataclass(frozen=True)
class AzureTTSConfig:
    base_url: str = 'https://{region}.tts.speech.microsoft.com'
    provider_id: str = 'azure-tts'
    timeout: int = 100
    long_timeout: int = 10000

class SubProviderManager:
    def __init__(self, db_client: AsyncIOMotorClient, provider_name: str):
        self.collection = db_client['db']['sub_providers']
        self.provider_name = provider_name

    async def get_available_provider(self, model: str) -> Optional[Dict[str, Any]]:
        sub_providers = await self.collection.find({
            'main_provider': self.provider_name,
            'models.api_name': {'$in': [model]},
            '$or': [
                {'working': True},
                {'working': {'$exists': False}}
            ]
        }).to_list(length=None)

        if not sub_providers:
            return None

        return min(
            sub_providers,
            key=lambda x: (x.get('usage', 0), x.get('last_used', 0))
        )

    async def update_provider(
        self,
        api_key: str,
        new_data: Dict[str, Any]
    ) -> None:
        update_data = {k: v for k, v in new_data.items() if k != '_id'}
        await self.collection.update_many(
            filter={'api_key': api_key},
            update={'$set': update_data}
        )

    async def disable_provider(
        self,
        api_key: str
    ) -> None:
        await self.collection.update_many(
            filter={'api_key': api_key},
            update={'$set': {'working': False}}
        )

class APIClient:
    def __init__(self, config: AzureTTSConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout
        )

    async def make_request(
        self,
        endpoint: str,
        method: str,
        sub_provider: Dict[str, Any],
        data: Dict[str, Any],
        stream: bool = False,
        files: Dict[str, Any] = None,
        long_timeout: bool = False
    ) -> httpx.Response:
        # Get region from sub_provider config, default to northcentralus
        region = sub_provider.get('region', 'northcentralus')
        base_url = self.config.base_url.format(region=region)
        
        headers = {
            'Ocp-Apim-Subscription-Key': sub_provider["api_key"],
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3',
            'User-Agent': 'api-oss'
        }
        
        # Convert OpenAI format to Azure TTS SSML format
        ssml_data = self._convert_to_ssml(data, sub_provider)
        
        url = f'{base_url}/cognitiveservices/v1'

        if long_timeout:
            self.client.timeout = self.config.long_timeout

        return await self.client.send(
            self.client.build_request(
                method=method,
                url=url,
                headers=headers,
                content=ssml_data
            ),
            stream=stream
        )

    def _convert_to_ssml(self, openai_data: Dict[str, Any], sub_provider: Dict[str, Any]) -> str:
        """Convert OpenAI audio request to Azure TTS SSML format"""
        text = openai_data.get('input', '')
        voice = openai_data.get('voice', 'alloy')
        
        # Map OpenAI voices to Azure TTS voices
        voice_mapping = {
            'alloy': 'en-US-AlloyTurboMultilingualNeural',
            'echo': 'en-US-EchoTurboMultilingualNeural',
            'fable': 'en-US-FableTurboMultilingualNeural',
            'onyx': 'en-US-OnyxTurboMultilingualNeural',
            'nova': 'en-US-NovaTurboMultilingualNeural',
            'shimmer': 'en-US-ShimmerTurboMultilingualNeural'
        }
        
        # Use custom voice if specified in sub_provider
        azure_voice = sub_provider.get('voice_mapping', {}).get(voice) or voice_mapping.get(voice, 'en-US-JennyNeural')
        
        # Get additional parameters
        rate = openai_data.get('speed', 1.0)
        if rate != 1.0:
            rate_percent = f"{int((rate - 1) * 100):+d}%"
        else:
            rate_percent = "+0%"
        
        ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="{azure_voice}">
        <prosody rate="{rate_percent}">
            {text}
        </prosody>
    </voice>
</speak>'''
        
        return ssml

class ResponseHandler:
    def __init__(self, config: AzureTTSConfig):
        self.config = config

    def create_error_response(
        self,
        message: str = 'Something went wrong. Try again later.',
        status_code: int = 500,
        error_type: str = 'invalid_response_error'
    ) -> PrettyJSONResponse:
        return PrettyJSONResponse(
            content={
                'error': {
                    'message': re.sub(r'[^/]+\.py', '', message),
                    'provider_id': self.config.provider_id,
                    'type': error_type,
                    'code': status_code
                }
            },
            status_code=status_code
        )

    def create_audio_response(self, content: bytes) -> Response:
        return Response(
            content=content,
            media_type='audio/mpeg',
            headers={'content-disposition': 'attachment;filename=audio.mp3'}
        )

class MetricsManager:
    def __init__(
        self,
        user_manager: UserManager,
        provider_manager: ProviderManager,
        sub_provider_manager: SubProviderManager
    ):
        self.user_manager = user_manager
        self.provider_manager = provider_manager
        self.sub_provider_manager = sub_provider_manager
        self.request_processor = RequestProcessor()

    async def update_user_credits(
        self,
        request: Request,
        model: str,
        character_count: int
    ) -> None:
        model_instance = Model.get_model(model)
        # For TTS, we charge based on character count
        request.state.user['credits'] -= model_instance.pricing.price + character_count
        await self.user_manager.update_user(request.state.user['user_id'], request.state.user)

    async def _update_provider_metrics(
        self,
        request: Request,
        model: str,
        elapsed: float,
        character_count: int
    ) -> None:
        latency = (elapsed / character_count) if character_count > 0 else 0

        request.state.provider['usage'][model] = request.state.provider['usage'].get(model, 0) + 1
        request.state.provider['latency'][model] = (
            (request.state.provider['latency'].get(model, 0) + latency) / 2 
            if request.state.provider['latency'].get(model, 0) != 0 
            else latency
        )

        await self.provider_manager.update_provider(
            request.state.provider_name,
            request.state.provider,
            model
        )

    async def _update_sub_provider_metrics(
        self,
        sub_provider: Dict[str, Any]
    ) -> None:
        sub_provider['usage'] = sub_provider.get('usage', 0) + 1
        sub_provider['last_used'] = time.time()
        await self.sub_provider_manager.update_provider(
            sub_provider['api_key'],
            sub_provider
        )

class EndpointHandler:
    def __init__(
        self,
        api_client: APIClient,
        response_handler: ResponseHandler,
        metrics_manager: MetricsManager,
        sub_provider_manager: SubProviderManager,
        provider_manager: ProviderManager,
        api_config: AzureTTSConfig,
        provider_config: ProviderConfig
    ):
        self.api_client = api_client
        self.response_handler = response_handler
        self.metrics_manager = metrics_manager
        self.sub_provider_manager = sub_provider_manager
        self.provider_manager = provider_manager
        self.api_config = api_config
        self.provider_config = provider_config
    
    async def _handle_error(
        self,
        request: Request,
        model: str,
        text: str
    ) -> None:
        await WebhookManager.send_to_webhook(
            request=request,
            is_error=True,
            model=model,
            pid=self.api_config.provider_id,
            exception=f'Error: {text}'
        )
        
        current_failure_count = request.state.provider['failures'].get(model, 0)
        request.state.provider['failures'][model] = current_failure_count + 1
        
        await self.provider_manager.update_provider(
            self.provider_config.name,
            request.state.provider
        )
    
    async def _handle_api_error(
        self,
        response: httpx.Response,
        stream: bool,
        sub_provider: Dict[str, Any],
        request: Request,
        model: str
    ) -> PrettyJSONResponse:
        if response.status_code in [401, 403, 404, 429]:
            await self.sub_provider_manager.disable_provider(
                sub_provider['api_key']
            )

        await self._handle_error(
            request,
            model,
            (await response.aread()).decode() if stream else response.text
        )
        return self.response_handler.create_error_response()

    async def handle_audio_speech(
        self,
        request: Request,
        model: str,
        input_text: str,
        sub_provider: Dict[str, Any],
        **kwargs
    ) -> Response:
        start_time = time.time()
        
        response = await self.api_client.make_request(
            endpoint='',  # Azure TTS doesn't use endpoint paths
            method='POST',
            sub_provider=sub_provider,
            data={'model': model, 'input': input_text, **kwargs},
            long_timeout=True
        )

        if response.status_code != 200:
            return await self._handle_api_error(
                response, False, sub_provider, request, model
            )

        character_count = len(input_text)
        elapsed = time.time() - start_time
        
        await self.metrics_manager.update_user_credits(
            request, model, character_count
        )
        
        await self.metrics_manager._update_provider_metrics(
            request, model, elapsed, character_count
        )
        
        await self.metrics_manager._update_sub_provider_metrics(sub_provider)

        return self.response_handler.create_audio_response(response.content)

class AzureTTS(BaseProvider):
    config = ProviderConfig(
        name='AzureTTS',
        supports_vision=False,
        supports_tool_calling=False,
        supports_real_streaming=False,
        free_models=[
            'azure-tts-standard'
        ],
        paid_models=[
            'azure-tts-neural',
            'azure-tts-neural-hd'
        ],
        early_access_models=[]
    )

    def __init__(self):
        super().__init__()
        self.api_config = AzureTTSConfig()
        self.user_manager = UserManager()
        self.provider_manager = ProviderManager()
        self.sub_provider_manager = SubProviderManager(
            AsyncIOMotorClient(settings.db_url),
            self.config.name
        )
        self.api_client = APIClient(self.api_config)
        self.response_handler = ResponseHandler(self.api_config)
        self.metrics_manager = MetricsManager(
            self.user_manager,
            self.provider_manager,
            self.sub_provider_manager
        )
        self.endpoint_handler = EndpointHandler(
            self.api_client,
            self.response_handler,
            self.metrics_manager,
            self.sub_provider_manager,
            self.provider_manager,
            self.api_config,
            self.config
        )

    @classmethod
    async def audio_speech(
        cls,
        request: Request,
        model: str,
        input: str,
        **kwargs
    ) -> Response:
        instance = cls()

        try:
            sub_provider = await instance.sub_provider_manager.get_available_provider(model)
            if not sub_provider:
                return instance.response_handler.create_error_response(
                    message='No sub-providers were found for the specified model. Try again later.',
                    status_code=503,
                    error_type='sub_provider_error'
                )

            return await instance.endpoint_handler.handle_audio_speech(
                request, model, input, sub_provider, **kwargs
            )

        except Exception:
            await instance.endpoint_handler._handle_error(
                request, model, traceback.format_exc()
            )
            return instance.response_handler.create_error_response(
                traceback.format_exc()
            )
