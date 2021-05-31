module "lambda_function_container_image" {
  source = "terraform-aws-modules/lambda/aws"

  function_name = "xtz"
  description   = "Lambda function to run XTZ crypto trading algorithm."

  create_package = false

  image_uri    = var.IMAGE_XTZ
  
  package_type = "Image"
  memory_size = 256
  timeout = 60
}

