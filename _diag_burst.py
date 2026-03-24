import os, sys, uuid, boto3
sys.path.insert(0, '.')
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'

from datetime import datetime, timezone, timedelta
from moto import mock_aws
from backend.functions.event_normalizer.normalizer import parse_cloudtrail_event
from backend.common.dynamodb_utils import put_item
from backend.functions.detection_engine.context import DetectionContext

identity_arn = 'arn:aws:iam::111111111111:user/attacker'
account_id = '111111111111'
table_name 