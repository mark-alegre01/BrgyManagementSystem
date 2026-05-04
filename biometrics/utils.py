from django.conf import settings
from django.utils.module_loading import import_string

def get_biometric_provider():
    """Factory function to load the configured biometric provider."""
    provider_path = getattr(settings, 'BIOMETRIC_PROVIDER', 'biometrics.stub.StubBiometricProvider')
    provider_class = import_string(provider_path)
    return provider_class()
