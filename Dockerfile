FROM public.ecr.aws/lambda/python:3.11

# Copy your app code into the Lambda task root
COPY ./app ${LAMBDA_TASK_ROOT}

# Install dependencies into the Lambda task root (so they are available in the container)
COPY requirements.txt .
RUN pip3 install --upgrade --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set the Lambda handler (file.function format, e.g. app.py → handler variable)
CMD ["app.lambda_handler"]
