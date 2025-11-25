from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Ajoute quelques en-têtes de sécurité compatibles avec l'existant (styles/JS inline).
    Bien activer HTTPS en production pour que ces directives soient pleinement efficaces.
    """
    def process_response(self, request, response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        # Policy permissive pour ne pas casser le front inline ; à durcir si possible.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self' data: blob:; "
            "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdn.jsdelivr.net/npm 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdn.jsdelivr.net/npm; "
            "img-src 'self' data: blob: https:;"
        )
        return response


class NoCacheForAuthMiddleware(MiddlewareMixin):
    """
    Ajoute des en-têtes no-cache à toutes les réponses pour éviter de revoir
    des pages protégées via le bouton Retour après déconnexion.
    """
    def process_response(self, request, response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
