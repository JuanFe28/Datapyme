from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

def make_survey_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt='datapyme-survey-token')

def generate_survey_token(secret: str, company_id: int) -> str:
    s = make_survey_serializer(secret)
    return s.dumps({'cid': int(company_id)})

def verify_survey_token(secret: str, token: str, max_age: int = 86400 * 30) -> int | None:
    s = make_survey_serializer(secret)
    try:
        data = s.loads(token, max_age=max_age)
        return int(data.get('cid'))
    except (BadSignature, SignatureExpired, TypeError, ValueError, KeyError):
        return None

