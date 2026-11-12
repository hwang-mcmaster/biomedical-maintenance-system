"""Unit-test-only identity fixture; production auth remains mandatory."""
from unittest.mock import patch
from fastapi.testclient import TestClient as Client
USER={'id':'00000000-0000-0000-0000-000000000001','name':'Unit fixture','email':'unit@example.test','role':'admin','is_active':True,'csrf_token':'unit-csrf'}
def setup_identity(case):
    case.enterContext(patch('app.auth.authenticate',return_value=USER))
    case.enterContext(patch('app.auth.audit'))
def TestClient(*args,**kwargs):
    kwargs['headers']={**kwargs.get('headers',{}),'Origin':'http://localhost:5173','X-CSRF-Token':'unit-csrf'}
    return Client(*args,**kwargs)
