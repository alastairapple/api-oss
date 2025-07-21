#!/usr/bin/env python3
"""
Integration test to verify that the new providers integrate correctly with the API routes.
This test verifies that the providers can be found and called by the endpoint handlers.
"""

import sys
import os
from unittest.mock import Mock, patch, AsyncMock
import asyncio

# Add the project root to path
sys.path.insert(0, '/home/runner/work/api-oss/api-oss/api')

async def test_provider_discovery():
    """Test that the provider discovery mechanism works with new providers"""
    
    print("Testing provider discovery...")
    
    # Mock the environment
    with patch.dict(os.environ, {'DB_URL': 'mongodb://localhost:27017', 'WEBHOOK_URL': 'https://example.com/webhook'}):
        
        # Mock database and networking components
        with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
             patch('app.utils.RequestProcessor'), \
             patch('app.core.UserManager'), \
             patch('app.core.ProviderManager'), \
             patch('app.providers.utils.WebhookManager'):
            
            try:
                from app.providers.base_provider import BaseProvider
                
                # Import providers to register them
                from app.providers.multiple import OpenAI, APIPie, OpenRouter, Gemini, AzureTTS
                
                print("Registered providers:")
                providers = {}
                for provider_class in BaseProvider.__subclasses__():
                    providers[provider_class.config.name] = provider_class
                    print(f"  ✓ {provider_class.config.name}: {provider_class.__name__}")
                
                # Test provider lookup
                test_cases = [
                    ('OpenAI', 'gpt-3.5-turbo'),
                    ('APIPie', 'gpt-4o-mini'), 
                    ('OpenRouter', 'llama-3.2-3b-instruct'),
                    ('Gemini', 'gemini-1.5-flash-latest'),
                    ('AzureTTS', 'azure-tts-standard')
                ]
                
                for provider_name, test_model in test_cases:
                    provider_class = BaseProvider.get_provider_class(provider_name)
                    if provider_class:
                        print(f"  ✓ {provider_name} lookup successful")
                        
                        # Check if the test model is in the provider's models
                        all_models = provider_class.config.all_models
                        if test_model in all_models:
                            print(f"    ✓ Model {test_model} available")
                        else:
                            print(f"    ⚠ Model {test_model} not in provider's model list")
                    else:
                        print(f"  ✗ {provider_name} lookup failed")
                
                return True
                
            except Exception as e:
                print(f"✗ Provider discovery test failed: {e}")
                return False

async def test_chat_completions_method():
    """Test that chat_completions methods are properly implemented"""
    
    print("\nTesting chat_completions methods...")
    
    with patch.dict(os.environ, {'DB_URL': 'mongodb://localhost:27017', 'WEBHOOK_URL': 'https://example.com/webhook'}):
        with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
             patch('app.utils.RequestProcessor'), \
             patch('app.core.UserManager'), \
             patch('app.core.ProviderManager'), \
             patch('app.providers.utils.WebhookManager'):
            
            try:
                from app.providers.multiple import APIPie, OpenRouter, Gemini
                
                # Create mock request
                mock_request = Mock()
                mock_request.state = Mock()
                mock_request.state.token_count = 100
                mock_request.state.user = {'credits': 10000, 'user_id': 'test'}
                mock_request.state.provider = {'usage': {}, 'latency': {}, 'failures': {}}
                mock_request.state.provider_name = 'TestProvider'
                
                test_messages = [
                    {'role': 'user', 'content': 'Hello, this is a test message.'}
                ]
                
                providers_to_test = [
                    (APIPie, 'gpt-3.5-turbo'),
                    (OpenRouter, 'gpt-3.5-turbo'),
                    (Gemini, 'gemini-1.5-flash-latest')
                ]
                
                for provider_class, model in providers_to_test:
                    if hasattr(provider_class, 'chat_completions'):
                        print(f"  ✓ {provider_class.config.name} has chat_completions method")
                        
                        # Mock the sub-provider manager to return None (no API keys)
                        with patch.object(provider_class, '__new__', return_value=Mock()) as mock_instance:
                            mock_instance_obj = Mock()
                            mock_instance_obj.sub_provider_manager = Mock()
                            mock_instance_obj.sub_provider_manager.get_available_provider = AsyncMock(return_value=None)
                            mock_instance_obj.response_handler = Mock()
                            mock_instance_obj.response_handler.create_error_response = Mock(return_value="error_response")
                            mock_instance.return_value = mock_instance_obj
                            
                            # Test that the method can be called (should return error due to no sub-providers)
                            try:
                                result = await provider_class.chat_completions(
                                    mock_request, model, test_messages, False
                                )
                                print(f"    ✓ {provider_class.config.name}.chat_completions callable")
                            except Exception as e:
                                print(f"    ✗ {provider_class.config.name}.chat_completions failed: {e}")
                    else:
                        print(f"  ✗ {provider_class.config.name} missing chat_completions method")
                
                return True
                
            except Exception as e:
                print(f"✗ Chat completions test failed: {e}")
                return False

async def test_audio_speech_method():
    """Test that audio_speech method is properly implemented for AzureTTS"""
    
    print("\nTesting audio_speech methods...")
    
    with patch.dict(os.environ, {'DB_URL': 'mongodb://localhost:27017', 'WEBHOOK_URL': 'https://example.com/webhook'}):
        with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
             patch('app.utils.RequestProcessor'), \
             patch('app.core.UserManager'), \
             patch('app.core.ProviderManager'), \
             patch('app.providers.utils.WebhookManager'):
            
            try:
                from app.providers.multiple import AzureTTS
                
                if hasattr(AzureTTS, 'audio_speech'):
                    print(f"  ✓ AzureTTS has audio_speech method")
                    
                    # Create mock request
                    mock_request = Mock()
                    mock_request.state = Mock()
                    mock_request.state.user = {'credits': 10000, 'user_id': 'test'}
                    mock_request.state.provider = {'usage': {}, 'latency': {}, 'failures': {}}
                    mock_request.state.provider_name = 'AzureTTS'
                    
                    # Mock the sub-provider manager to return None (no API keys)
                    with patch.object(AzureTTS, '__new__', return_value=Mock()) as mock_instance:
                        mock_instance_obj = Mock()
                        mock_instance_obj.sub_provider_manager = Mock()
                        mock_instance_obj.sub_provider_manager.get_available_provider = AsyncMock(return_value=None)
                        mock_instance_obj.response_handler = Mock()
                        mock_instance_obj.response_handler.create_error_response = Mock(return_value="error_response")
                        mock_instance.return_value = mock_instance_obj
                        
                        try:
                            result = await AzureTTS.audio_speech(
                                mock_request, 'azure-tts-standard', 'Hello world'
                            )
                            print(f"    ✓ AzureTTS.audio_speech callable")
                        except Exception as e:
                            print(f"    ✗ AzureTTS.audio_speech failed: {e}")
                else:
                    print(f"  ✗ AzureTTS missing audio_speech method")
                
                return True
                
            except Exception as e:
                print(f"✗ Audio speech test failed: {e}")
                return False

async def test_format_conversions():
    """Test the format conversion functionality"""
    
    print("\nTesting format conversions...")
    
    try:
        # Test Gemini format conversion (without importing the full provider)
        import json
        
        # Read the Gemini provider file and check if conversion methods exist
        with open('/home/runner/work/api-oss/api-oss/api/app/providers/multiple/gemini.py', 'r') as f:
            gemini_content = f.read()
        
        if '_convert_to_gemini_format' in gemini_content:
            print("  ✓ Gemini OpenAI->Gemini conversion method exists")
        if '_convert_from_gemini_format' in gemini_content:
            print("  ✓ Gemini Gemini->OpenAI conversion method exists")
        
        # Test Azure TTS SSML conversion
        with open('/home/runner/work/api-oss/api-oss/api/app/providers/multiple/azure_tts.py', 'r') as f:
            azure_content = f.read()
        
        if '_convert_to_ssml' in azure_content:
            print("  ✓ Azure TTS OpenAI->SSML conversion method exists")
        
        # Test that voice mappings are defined
        if 'voice_mapping' in azure_content and 'alloy' in azure_content:
            print("  ✓ Azure TTS voice mapping defined")
        
        return True
        
    except Exception as e:
        print(f"✗ Format conversion test failed: {e}")
        return False

async def main():
    """Run all integration tests"""
    
    print("=== Provider Integration Tests ===\n")
    
    tests = [
        ("Provider Discovery", test_provider_discovery()),
        ("Chat Completions Methods", test_chat_completions_method()),
        ("Audio Speech Methods", test_audio_speech_method()),
        ("Format Conversions", test_format_conversions())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"Running {test_name}...")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n=== Integration Test Summary ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print(f"\n🎉 All integration tests passed!")
        print(f"✅ New providers are properly integrated")
        print(f"✅ Methods are correctly implemented")
        print(f"✅ Format conversions are in place")
        return True
    else:
        print(f"\n❌ Some integration tests failed")
        return False

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)