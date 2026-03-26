bucket         = "<REPLACE: your Terraform state S3 bucket name>"
key            = "radius/prod/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "radius-terraform-locks"
encrypt        = true
