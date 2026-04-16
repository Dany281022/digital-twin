from mangum import Mangum
from server import app
lambda_handler = Mangum(app)
handler = lambda_handler
