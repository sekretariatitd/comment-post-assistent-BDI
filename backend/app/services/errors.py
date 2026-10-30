"""Service-layer errors. app.main maps them to HTTP responses so routes stay thin."""


class ServiceError(Exception):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class InvalidInputError(ServiceError):
    status_code = 422
