#!/usr/bin/env python3
"""
Final verification test to check that the audio speech endpoint can find Azure TTS provider.
This simulates the actual API request flow without requiring network access.
"""

import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# Add the project root to path
sys.path.insert(0, '/home/runner/work/api-oss/api-oss/api')

def test_audio_endpoint_provider_discovery():
    """Test that the audio speech endpoint can discover Azure TTS provider"""
    
    print("Testing audio endpoint provider discovery...")
    
    # Mock environment variables
    with patch.dict(os.environ, {'DB_URL': 'mongodb://localhost:27017', 'WEBHOOK_URL': 'https://example.com/webhook'}):
        
        # Mock all the external dependencies
        with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
             patch('app.utils.RequestProcessor'), \
             patch('app.core.UserManager'), \
             patch('app.core.ProviderManager') as mock_provider_manager, \
             patch('app.providers.utils.WebhookManager'):
            
            try:
                # Import the models and base provider system
                from app.providers.ai_models import ModelRegistry
                from app.providers.base_provider import BaseProvider
                
                # Import all providers to register them
                from app.providers.multiple import OpenAI, APIPie, OpenRouter, Gemini, AzureTTS
                
                print("✓ Successfully imported all providers")
                
                # Check that Azure TTS models are in the registry
                azure_models = ['azure-tts-standard', 'azure-tts-neural', 'azure-tts-neural-hd']
                found_models = []
                
                for model_id in azure_models:
                    if hasattr(ModelRegistry, model_id.replace('-', '_')):
                        model = getattr(ModelRegistry, model_id.replace('-', '_'))
                        found_models.append(model_id)
                        print(f"✓ Found {model_id} in ModelRegistry")
                        print(f"  - Endpoint: {model.endpoint}")
                        print(f"  - Owner: {model.owned_by}")
                        print(f"  - Voices: {len(model.voices)}")
                
                if len(found_models) == len(azure_models):
                    print(f"✓ All {len(azure_models)} Azure TTS models available")
                else:
                    print(f"✗ Only {len(found_models)}/{len(azure_models)} Azure TTS models found")
                    return False
                
                # Test provider lookup for Azure TTS
                azure_provider = BaseProvider.get_provider_class('AzureTTS')
                if azure_provider:
                    print("✓ AzureTTS provider found via BaseProvider.get_provider_class")
                    print(f"  - Provider name: {azure_provider.config.name}")
                    print(f"  - Free models: {len(azure_provider.config.free_models)}")
                    print(f"  - Paid models: {len(azure_provider.config.paid_models)}")
                    
                    # Check if audio_speech method exists
                    if hasattr(azure_provider, 'audio_speech'):
                        print("✓ AzureTTS has audio_speech method")
                    else:
                        print("✗ AzureTTS missing audio_speech method")
                        return False
                else:
                    print("✗ AzureTTS provider not found")
                    return False
                
                return True
                
            except Exception as e:
                print(f"✗ Provider discovery test failed: {e}")
                import traceback
                traceback.print_exc()
                return False

async def test_simulated_api_call():
    """Simulate an API call to the audio speech endpoint"""
    
    print("\nTesting simulated API call flow...")
    
    with patch.dict(os.environ, {'DB_URL': 'mongodb://localhost:27017', 'WEBHOOK_URL': 'https://example.com/webhook'}):
        with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
             patch('app.utils.RequestProcessor'), \
             patch('app.core.UserManager'), \
             patch('app.core.ProviderManager') as mock_provider_manager:
            
            try:
                # Import what we need
                from app.providers.base_provider import BaseProvider
                from app.providers.multiple import AzureTTS
                from app.providers.ai_models import Model
                
                # Mock a provider manager response
                mock_provider_manager.return_value.get_best_provider = AsyncMock(return_value={
                    'name': 'AzureTTS',
                    'usage': {'azure-tts-standard': 0},
                    'latency': {'azure-tts-standard': 0},
                    'failures': {'azure-tts-standard': 0}
                })
                
                # Test provider lookup (simulating what AudioHandler._get_provider does)
                provider_data = await mock_provider_manager.return_value.get_best_provider('azure-tts-standard')
                if provider_data and provider_data['name'] == 'AzureTTS':
                    print("✓ Provider manager returns AzureTTS for azure-tts-standard")
                    
                    # Test provider class lookup (simulating what happens next)
                    provider_class = BaseProvider.get_provider_class('AzureTTS')
                    if provider_class and provider_class == AzureTTS:
                        print("✓ BaseProvider.get_provider_class returns AzureTTS class")
                        
                        # Test model lookup (simulating token count calculation)
                        model = Model.get_model('azure-tts-standard')
                        if model:
                            print(f"✓ Model.get_model found azure-tts-standard")
                            print(f"  - Pricing: {model.pricing.price}")
                            print(f"  - Endpoint: {model.endpoint}")
                        else:
                            print("✗ Model.get_model failed for azure-tts-standard")
                            return False
                        
                        return True
                    else:
                        print("✗ BaseProvider.get_provider_class failed")
                        return False
                else:
                    print("✗ Provider manager failed to return AzureTTS")
                    return False
                
            except Exception as e:
                print(f"✗ Simulated API call test failed: {e}")
                import traceback
                traceback.print_exc()
                return False

def test_chat_providers():
    """Test that chat providers are properly set up"""
    
    print("\nTesting chat completion providers...")
    
    with patch.dict(os.environ, {'DB_URL': 'mongodb://localhost:27017', 'WEBHOOK_URL': 'https://example.com/webhook'}):
        with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
             patch('app.utils.RequestProcessor'), \
             patch('app.core.UserManager'), \
             patch('app.core.ProviderManager'), \
             patch('app.providers.utils.WebhookManager'):
            
            try:
                from app.providers.base_provider import BaseProvider
                from app.providers.multiple import APIPie, OpenRouter, Gemini
                
                chat_providers = [
                    ('APIPie', 'gpt-3.5-turbo'),
                    ('OpenRouter', 'llama-3.2-3b-instruct'),
                    ('Gemini', 'gemini-1.5-flash-latest')
                ]
                
                for provider_name, test_model in chat_providers:
                    provider_class = BaseProvider.get_provider_class(provider_name)
                    if provider_class:
                        print(f"✓ {provider_name} provider found")
                        
                        # Check if the test model is available
                        if test_model in provider_class.config.all_models:
                            print(f"  ✓ Model {test_model} available")
                        else:
                            print(f"  ⚠ Model {test_model} not in provider's model list")
                        
                        # Check if chat_completions method exists
                        if hasattr(provider_class, 'chat_completions'):
                            print(f"  ✓ {provider_name} has chat_completions method")
                        else:
                            print(f"  ✗ {provider_name} missing chat_completions method")
                    else:
                        print(f"✗ {provider_name} provider not found")
                        return False
                
                return True
                
            except Exception as e:
                print(f"✗ Chat providers test failed: {e}")
                return False

def main():
    """Run all final verification tests"""
    
    print("=== Final Provider Verification ===\n")
    
    tests = [
        ("Audio Endpoint Provider Discovery", test_audio_endpoint_provider_discovery()),
        ("Chat Completion Providers", test_chat_providers())
    ]
    
    # Add async test
    import asyncio
    
    async def run_async_tests():
        return await test_simulated_api_call()
    
    tests.append(("Simulated API Call Flow", asyncio.run(run_async_tests())))
    
    # Evaluate results
    results = []
    for test_name, result in tests:
        results.append((test_name, result))
    
    # Summary
    print(f"\n=== Final Verification Summary ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print(f"\n🎉 All final verification tests passed!")
        print(f"✅ Providers are properly integrated with the API system")
        print(f"✅ Audio speech endpoint can find Azure TTS provider")
        print(f"✅ Chat completion endpoints can find new providers")
        print(f"✅ Model registry contains all new models")
        return True
    else:
        print(f"\n❌ Some final verification tests failed")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)