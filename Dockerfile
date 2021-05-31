# https://hub.docker.com/r/amazon/aws-lambda-python 
FROM public.ecr.aws/lambda/python:3.8

COPY src/requirements.txt /${LAMBDA_TASK_ROOT}/requirements.txt
RUN cat ${LAMBDA_TASK_ROOT}/requirements.txt | xargs -n 1 python3 -m pip install
COPY src/XTZUSDT.py ${LAMBDA_TASK_ROOT}/XTZUSDT.py
RUN mkdir /${LAMBDA_TASK_ROOT}/util
COPY util/* ${LAMBDA_TASK_ROOT}/util/

CMD ["XTZUSDT.lambda_handler"]