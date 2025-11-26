import boto3 
bedrock = boto3.client(service_name='bedrock')


if __name__ == "__main__":
    print(bedrock.get_foundation_model(modelIdentifier='amazon.nova-lite-v1:0'))