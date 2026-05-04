from abc import ABC, abstractmethod

class BiometricProvider(ABC):
    """Abstract base class for biometric providers."""

    @abstractmethod
    def enroll(self, user_id, template_data):
        """Enroll a new biometric template for a user."""
        pass

    @abstractmethod
    def verify(self, user_id, scan_data):
        """Verify a user against a provided scan."""
        pass

    @abstractmethod
    def delete_template(self, user_id):
        """Delete a biometric template for a user."""
        pass
