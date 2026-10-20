docker pull python:latest
docker pull mongo:latest
docker pull redis:latest
docker pull trufflesuite/ganache-cli:latest

docker build -t authentication -f authentication.dockerfile .
docker build -t employee -f employee.dockerfile .
docker build -t director -f director.dockerfile .

python -m venv .venv
.\.venv\Scripts\activate
pip install py-solc-x

python compile_voters.py

kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f mongo.yaml
kubectl apply -f redis.yaml
kubectl apply -f ganache.yaml
kubectl apply -f authentication.yaml
kubectl apply -f employee.yaml
kubectl apply -f director.yaml
