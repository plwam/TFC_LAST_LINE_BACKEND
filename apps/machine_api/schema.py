"""
Documentation OpenAPI de l'authentification HMAC (drf-spectacular).

Le schéma standard OpenAPI ne sait pas décrire une signature HMAC « maison » : sans cette
extension, Swagger afficherait les endpoints machine comme non authentifiés, ce qui induirait
les développeurs en erreur. On déclare donc un schéma `apiKey` sur l'en-tête
`X-ExamSDK-Signature` et on documente l'en-tête compagnon dans la description.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class HMACAuthenticationScheme(OpenApiAuthenticationExtension):
    """Déclare le schéma d'authentification HMAC dans le document OpenAPI."""

    target_class = "apps.machine_api.authentication.HMACAuthentication"
    name = "HMAC"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-ExamSDK-Signature",
            "description": (
                "Signature HMAC-SHA256 (hexadécimal) de la chaîne canonique, calculée avec la "
                "`secret_key` du projet. Doit être accompagnée de l'en-tête "
                "`X-ExamSDK-Public-Key` (la `public_key` du projet, non secrète) et de la "
                "valeur `issued_at` (epoch secondes) présente dans le corps ou l'URL. "
                "Chaîne canonique : `project_id|exam_id|student_id|issued_at` à la création "
                "d'une session ; `project_id|session_id|issued_at` pour les événements ; "
                "`project_id|sdk-logs|issued_at` pour le journal du SDK."
            ),
        }
