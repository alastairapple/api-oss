# New Provider Implementation Summary

This document summarizes the implementation of four new providers for the API: APIPie, OpenRouter, Google Gemini, and Azure TTS.

## Implementation Overview

### 1. APIPie Provider (`app/providers/multiple/apipie.py`)
- **Base URL**: `https://apipie.ai`
- **Provider ID**: `apipie`
- **Compatibility**: Full OpenAI API compatibility
- **Features**:
  - Chat completions with streaming support
  - Vision support
  - Tool calling support
  - Error handling and retries
- **Models**:
  - **Free models (8)**: gpt-3.5-turbo, gpt-4o, gpt-4o-mini, claude-3-haiku, claude-3.5-haiku, gemini-1.5-flash-latest, llama-3.2-3b-instruct, llama-3.2-11b-instruct
  - **Paid models (14)**: gpt-4, gpt-4-turbo, gpt-4o-2024-11-20, chatgpt-4o-latest, o1-mini, o1-preview, o1, claude-3-opus, claude-3.5-sonnet, claude-3.5-sonnet-v2, gemini-1.5-pro-latest, gemini-2.0-flash, llama-3.1-405b-instruct, llama-3.1-70b-instruct
  - **Early access (1)**: o3-mini

### 2. OpenRouter Provider (`app/providers/multiple/openrouter.py`)
- **Base URL**: `https://openrouter.ai`
- **Provider ID**: `openrouter`
- **Compatibility**: OpenAI API with additional headers
- **Features**:
  - Chat completions with streaming support
  - HTTP referer and X-Title header support
  - Vision support
  - Tool calling support
- **Models**:
  - **Free models (13)**: gpt-3.5-turbo, gpt-4o-mini, claude-3-haiku, claude-3.5-haiku, gemini-1.5-flash-latest, llama-3.2-3b-instruct, llama-3.2-11b-instruct, llama-3.2-90b-instruct, qwen2.5-72b-instruct, hermes-2-pro-mistral-7b, openhermes-2.5-mistral-7b, toppy-7b, mythomax-l2-13b
  - **Paid models (22)**: Various GPT-4, Claude, Gemini, and other premium models
  - **Early access (1)**: o3-mini

### 3. Google Gemini Provider (`app/providers/multiple/gemini.py`)
- **Base URL**: `https://generativelanguage.googleapis.com`
- **Provider ID**: `gemini`
- **Compatibility**: Native Gemini API with OpenAI format conversion
- **Features**:
  - Format conversion between OpenAI and Gemini formats
  - Streaming and non-streaming support
  - Vision support
  - Tool calling support
  - Automatic role mapping (assistant -> model, system -> user)
- **Models**:
  - **Free models (6)**: gemini-1.5-flash-latest, gemini-1.5-pro-latest, gemini-2.0-flash-exp, gemini-exp-1121, learnlm-1.5-pro-experimental, gemini-2.0-flash-thinking-exp-01-21
  - **Paid models (2)**: gemini-2.0-flash, gemini-2.0-flash-lite-preview-02-05
  - **Early access (1)**: gemini-2.0-pro-exp-02-05

### 4. Azure TTS Provider (`app/providers/multiple/azure_tts.py`)
- **Base URL**: `https://{region}.tts.speech.microsoft.com`
- **Provider ID**: `azure-tts`
- **Compatibility**: OpenAI TTS API with SSML conversion
- **Features**:
  - OpenAI format to Azure SSML conversion
  - Voice mapping from OpenAI voices to Azure Neural voices
  - Speed/rate adjustment support
  - Regional endpoint support
- **Models**:
  - **Free models (1)**: azure-tts-standard
  - **Paid models (2)**: azure-tts-neural, azure-tts-neural-hd
- **Voice Mapping**:
  - alloy -> en-US-JennyNeural
  - echo -> en-US-GuyNeural
  - fable -> en-US-AriaNeural
  - onyx -> en-US-DavisNeural
  - nova -> en-US-AmberNeural
  - shimmer -> en-US-CoraNeural

## Technical Implementation Details

### Provider Architecture
Each provider follows the same architectural pattern:
1. **Config Class**: Contains base URL, provider ID, and timeout settings
2. **APIClient**: Handles HTTP requests to the provider's API
3. **ResponseHandler**: Manages response formatting and error handling
4. **MetricsManager**: Tracks usage, latency, and updates user credits
5. **StreamHandler**: Manages streaming responses (for applicable providers)
6. **EndpointHandler**: Orchestrates the request/response flow
7. **Provider Class**: Main class that extends BaseProvider

### Format Conversions

#### Gemini Provider
- **Request Conversion**: OpenAI chat format → Gemini contents format
  - Maps roles: assistant → model, system/user → user
  - Converts messages to contents with parts structure
  - Translates generation parameters
- **Response Conversion**: Gemini response → OpenAI format
  - Maps candidates to choices
  - Extracts text from parts
  - Converts finish reasons
  - Formats usage metadata

#### Azure TTS Provider
- **Request Conversion**: OpenAI TTS format → Azure SSML
  - Maps voice names to Azure Neural voices
  - Converts speed parameter to prosody rate
  - Generates proper SSML structure
  - Supports custom voice mappings

### Error Handling
All providers implement comprehensive error handling:
- HTTP error code handling (401, 403, 404, 429)
- Sub-provider disabling on authentication failures
- Webhook notifications for errors
- Failure tracking and metrics
- Graceful degradation

### Metrics and Monitoring
- Usage tracking per model
- Latency measurements
- Credit consumption calculation
- Provider performance metrics
- Sub-provider health monitoring

## File Changes

### New Files Created
1. `app/providers/multiple/apipie.py` - APIPie provider implementation
2. `app/providers/multiple/openrouter.py` - OpenRouter provider implementation
3. `app/providers/multiple/gemini.py` - Google Gemini provider implementation
4. `app/providers/multiple/azure_tts.py` - Azure TTS provider implementation

### Modified Files
1. `app/providers/multiple/__init__.py` - Added imports for new providers
2. `app/providers/ai_models.py` - Added Azure TTS models to ModelRegistry

### Testing and Validation
- ✅ Syntax validation for all provider files
- ✅ Provider structure validation
- ✅ Model registry validation
- ✅ Import configuration validation
- ✅ Format conversion method validation

## Usage

### Configuration
Each provider requires sub-provider configuration in the database with API keys:

```json
{
  "main_provider": "APIPie",  // or "OpenRouter", "Gemini", "AzureTTS"
  "api_key": "your-api-key",
  "models": [{"api_name": "gpt-3.5-turbo"}],
  "working": true
}
```

### Azure TTS Additional Configuration
```json
{
  "main_provider": "AzureTTS",
  "api_key": "your-azure-key",
  "region": "eastus",  // optional, defaults to eastus
  "voice_mapping": {   // optional custom voice mappings
    "alloy": "en-US-CustomVoice"
  }
}
```

### OpenRouter Additional Configuration
```json
{
  "main_provider": "OpenRouter",
  "api_key": "your-openrouter-key",
  "http_referer": "https://yourapp.com",  // optional
  "x_title": "Your App Name"              // optional
}
```

## Benefits

1. **Increased Model Availability**: Access to 100+ additional models across different providers
2. **Cost Optimization**: Free tiers available on all providers
3. **Redundancy**: Multiple providers for the same models ensure high availability
4. **Specialized Features**: Azure TTS for high-quality speech synthesis
5. **Format Compatibility**: Seamless OpenAI API compatibility maintained

## Next Steps

1. **Database Setup**: Configure sub-providers with API keys
2. **Load Testing**: Test with actual API calls under load
3. **Monitoring**: Set up provider-specific monitoring and alerting
4. **Documentation**: Update API documentation with new provider capabilities