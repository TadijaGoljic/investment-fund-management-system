FROM python:latest

COPY ./requirements.txt ./requirements.txt

RUN pip install -r requirements.txt
RUN python -c "import solcx; solcx.install_solc('0.8.18')"

COPY ./director.py ./director.py
COPY ./configuration.py ./configuration.py
COPY ./models.py ./models.py
COPY ./utils.py ./utils.py
COPY ./compile_voters.py ./compile_voters.py
COPY ./voters.sol ./voters.sol

ENTRYPOINT ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5002"]