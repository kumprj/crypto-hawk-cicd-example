terraform {
  backend "s3" {
    bucket = "crypto-hawk-tf-state-files"
    key = "global/s3/xtz-state-file/terraform.tfstate"
    region = "us-east-2"
    dynamodb_table = "terraform_lock_state"
    encrypt = true
  }
}