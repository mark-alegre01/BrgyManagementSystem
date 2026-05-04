from .base import BiometricProvider

class StubBiometricProvider(BiometricProvider):
    """Stub implementation of a biometric provider for no-op responses."""

    def enroll(self, user_id, template_data):
        return {"status": "success", "message": "Stub: Enrolled template for user {}".format(user_id)}

    def verify(self, user_id, scan_data):
        return {"status": "success", "message": "Stub: Verified user {}".format(user_id)}

    def delete_template(self, user_id):
        return {"status": "success", "message": "Stub: Deleted template for user {}".format(user_id)}
