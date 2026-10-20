FROM python:latest

COPY ./authentication.py ./authentication.py
COPY ./configuration.py ./configuration.py
COPY ./models.py ./models.py
COPY ./utils.py ./utils.py

COPY ./requirements.txt ./requirements.txt

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]