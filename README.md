# Containerized Movie Explorer

The explorer is a lightweight, decoupled three-tier microservices application designed for isolated container execution across a shared Docker bridge network (movie-net). It enables users to browse and filter a database of movies dynamically by genre (Drama, Comedy, Thriller).

## Architecture Components

**Frontend (movie-ui):**  A lightweight Nginx web server hosting a plain HTML/JavaScript interface. It executes asynchronous fetch calls from the client's browser to retrieve dynamic movie data.

**Backend API (movie-api):** A Python Flask REST API wrapped with Flask-CORS. It handles incoming HTTP requests on port 5001, queries the MongoDB instance over the internal container network, and enforces _id field exclusion for clean JSON serialization.

**Database (movie-db):** A MongoDB 6.0 instance pre-seeded with initial movie documents using mongoimport. It persists data inside the movies_db database on standard port 27017.

| Service | Container Name | Technology | Internal Port | Host Port | Primary Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend** | `movie-ui` | Nginx / HTML / JS | `80` | `8181` | Serves the UI to the client browser |
| **Backend** | `movie-api` | Python 3.10 / Flask | `5000` | `5001` | Processes API requests and queries MongoDB |
| **Database** | `movie-db` | MongoDB 6.0 | `27017` | `27017` | Stores movie documents in `movies_db` |

```
+-----------------------------------------------------------------------------------+
|                                     HOST SYSTEM                                   |
|                                                                                   |
|   +-------------------+                         +-----------------------------+   |
|   |   Web Browser     |                         |    macOS AirPlay Service    |   |
|   |  (Client Machine) |                         |  (Binds to Port 5000: 403)  |   |
|   +---------+---------+                         +-----------------------------+   |
|             |                                                                     |
|             | HTTP Request (http://localhost:8181)                                |
|             v                                                                     |
|   +---------------------------------------------------------------------------+   |
|   |                         DOCKER ENGINE / CONTAINER NETWORK                 |   |
|   |                                                                           |   |
|   |  +--------------------+                                                   |   |
|   |  |     movie-ui       |                                                   |   |
|   |  |  (Nginx Web Server)|                                                   |   |
|   |  +--------------------+                                                   |   |
|   |                                                                           |   |
|   |  Client-Side API Fetch (http://localhost:5001/api/movies?category=...)    |   |
|   |  +-----------------------------------+                                    |   |
|   |  |                                   |                                    |   |
|   |  v                                   v                                    |   |
|   |  +--------------------+  movie-net   +--------------------+               |   |
|   |  |     movie-api      |------------->|      movie-db      |               |   |
|   |  |  (Python/Flask)    |  TCP:27017   |     (MongoDB)      |               |   |
|   |  +--------------------+              +--------------------+               |   |
|   |    Container Port: 5000                Container Port: 27017              |   |
|   |    Host Port: 5001                     Host Port: 27017                   |   |
|   |                                                                           |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

## Step 1: Create the Isolated Bridge Network
```
docker network create movie-net
```

## Step 2: Spin up MongoDB Container & Seed Initial Data
```
docker run -d \
  --name movie-db \
  --network movie-net \
  -p 27017:27017 \
  mongo:6.0

docker cp mongo/init.json movie-db:/tmp/init.json

docker exec -i movie-db mongoimport \
  --db movies_db \
  --collection movies \
  --file /tmp/init.json \
  --jsonArray

docker exec -it movie-db mongosh movies_db --eval "db.movies.find()"
```

## Step 3: Build & Run Python Backend API Container
```
docker build -t movie-backend backend/

docker run -d \
  --name movie-api \
  --network movie-net \
  -p 5001:5000 \
  movie-backend

docker logs --tail 50 movie-api

docker exec -it movie-api python -c "
from pymongo import MongoClient
client = MongoClient('mongodb://movie-db:27017/')
db = client['movies_db']
print(list(db.movies.find({}, {'_id': 0})))
"
```

## Step 4: Build & Run JavaScript Frontend Container
```
docker build -t movie-frontend frontend/

docker run -d \
  --name movie-ui \
  --network movie-net \
  -p 8181:80 \
  movie-frontend
```

## Step5. Verification & Testing
```

http://localhost:8181/

curl -s "http://localhost:5001/api/movies?category=comedy"
```

## Step 6: Run Python Tests and Analyze Code with SonarQube (WSL)

Run these commands in a WSL terminal from this directory. The tests use `mongomock`, so they run against an in-memory MongoDB simulation and do not require the `movie-db` container.

### Run the Python tests

Create and activate a Linux virtual environment. If creating it fails because `ensurepip` is unavailable, install the venv package for the Python version shown by `python3 --version` (for example, `python3.10-venv`):

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip

python3 -m venv .venv-wsl
source .venv-wsl/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt -r mongo/requirements.txt 'setuptools<81'
python -m pytest backend/test_app.py mongo/test_db.py -v
```

Activate the environment again in a later terminal session before running tests:

```bash
source .venv-wsl/bin/activate
python -m pytest backend/test_app.py mongo/test_db.py -v
```

### Configure SonarQube once

The SonarQube server should be running and reachable at `http://localhost:9000`. Create a local project in the SonarQube UI with the project key `movie-app`, then generate an analysis token. Keep the token private; do not add it to this repository.

Ensure the Docker network exists and connect the SonarQube container to it. These commands assume the server container is named `sonarqube`:

```bash
docker network inspect movie-net >/dev/null 2>&1 || docker network create movie-net
docker network connect movie-net sonarqube
```

If `docker network connect` reports that the container is already connected, that is fine.

Create `sonar-project.properties` in this directory:

```properties
sonar.projectKey=movie-app
sonar.projectName=Movie Explorer
sonar.sourceEncoding=UTF-8
sonar.sources=backend/app.py
sonar.tests=backend/test_app.py,mongo/test_db.py
sonar.exclusions=**/.venv/**,**/.venv-wsl/**,**/__pycache__/**,**/.pytest_cache/**
```

### Run a code analysis

From this directory, enter the token without writing it into a file, then run the scanner container:

```bash
read -s -p "SonarQube token: " SONAR_TOKEN
echo
export SONAR_TOKEN

docker run --rm --network movie-net \
  -e SONAR_HOST_URL="http://sonarqube:9000" \
  -e SONAR_TOKEN \
  -v "$PWD:/usr/src" \
  sonarsource/sonar-scanner-cli
```

When the scanner completes successfully, view the analysis in the `movie-app` project at `http://localhost:9000`. Run the `pytest` command separately; SonarScanner analyzes the code but does not execute tests.

### Maintain the SonarQube container

Check its status and recent startup logs:

```bash
docker ps -a --filter name=sonarqube
docker logs --tail 100 sonarqube
```

Stop the server when it is not needed and start it again later; its Docker volumes preserve SonarQube data:

```bash
docker stop sonarqube
docker start sonarqube
```

After starting it, wait for SonarQube to become available at `http://localhost:9000` before running the scanner. If the container has not been created yet, create it once with persistent volumes:

```bash
docker run -d --name sonarqube --network movie-net -p 9000:9000 \
  -v sonarqube_data:/opt/sonarqube/data \
  -v sonarqube_extensions:/opt/sonarqube/extensions \
  -v sonarqube_logs:/opt/sonarqube/logs \
  sonarqube:community
```

## Step 7. Clean up the manually-created stack
```
# Stop and remove all 3 running containers
docker rm -f movie-ui movie-api movie-db

# Delete custom Docker images
docker rmi movie-frontend movie-backend

# SonarQube may also be connected to movie-net. Disconnect it before removing
# the network; the SonarQube container and its volumes are kept.
docker network disconnect movie-net sonarqube

# Delete the custom network
docker network rm movie-net

# Optional remove unused system caches and dangling resources
docker system prune -f
```

## Step 8: Run the Complete Application with Docker Compose

The Compose setup below is the recommended way to run the frontend, backend, MongoDB, SonarQube, and the Nginx reverse proxy together. Run the commands from this directory in WSL. The proxy is published on port `8080`; SonarQube is published on port `9000`. MongoDB and the backend are only reachable inside the Compose network.

The Compose MongoDB database uses its own persistent volume and is seeded from `mongo/init.json` on startup. The seed operation uses movie titles to upsert records, so starting the stack again does not add duplicate seed documents. The SonarQube volumes are named `sonarqube_data`, `sonarqube_extensions`, and `sonarqube_logs` to reuse volumes created by the earlier `docker run` instructions.

### Prepare and start the stack

SonarQube requires a higher Linux memory-map limit. Set it in WSL before starting the stack:

```bash
sudo sysctl -w vm.max_map_count=524288
```

If the manually-created SonarQube container is still running on port `9000`, stop it first. Do not remove its volumes; Compose reuses them:

```bash
docker stop sonarqube
```

Build the app images and start the services:

```bash
cp .env.example .env
# Edit .env and set DOCKERHUB_USERNAME to your Docker Hub account.
docker compose up --build -d
docker compose ps
```

Open the app at `http://localhost:8080` and SonarQube at `http://localhost:9000`. The reverse proxy sends `/api/` requests to the backend and all other paths to the frontend. Check startup output if a service is not healthy:

```bash
docker compose logs --tail 100
docker compose logs -f db-seed backend proxy sonarqube
```

Press `Ctrl+C` to stop following logs; this does not stop the containers.

The reverse proxy image includes `nginx/default.conf`. After changing that file, rebuild and recreate the proxy:

```bash
docker compose up -d --build --force-recreate proxy
```

### Verify the app and run its tests

```bash
curl -i "http://localhost:8080/api/movies?category=comedy"
python -m pytest backend/test_app.py mongo/test_db.py -v
```

Activate `.venv-wsl` before running pytest if you created it in Step 6:

```bash
source .venv-wsl/bin/activate
```

### Run SonarQube analysis

Create the `movie-app` project in SonarQube and generate an analysis token if you have not already done so. From this directory, enter the token without saving it in a file, then run the optional scanner service:

```bash
read -s -p "SonarQube token: " SONAR_TOKEN
echo
export SONAR_TOKEN
docker compose --profile analysis run --rm scanner
unset SONAR_TOKEN
```

Review the analysis in the `movie-app` project at `http://localhost:9000`. The scanner analyzes code but does not run pytest.

### Stop, restart, and remove the stack

Stop the containers while preserving database and SonarQube data:

```bash
docker compose stop
```

Start the existing containers again:

```bash
docker compose start
```

To remove the Compose containers and its default network while keeping named volumes:

```bash
docker compose down
```

To also permanently delete the MongoDB and SonarQube stored data, explicitly remove the volumes:

```bash
docker compose down --volumes
```
## Step 9: GitHub Actions CI/CD (trunk-based)

The repository uses a trunk-based flow: work in short-lived branches, open pull requests to `main`, and merge only after the CI checks pass. Every push to `main` runs tests and SonarQube analysis, builds and publishes versioned backend and frontend images to Docker Hub, then deploys that exact version with Docker Compose on your Linux self-hosted runner. Image tags use the GitHub run number plus the commit prefix (for example `14-a1b2c3d`). `latest` is also updated for convenience; deployments use the immutable version tag.

### Configure the machine runner and secrets

1. In GitHub, add a self-hosted **Linux** Actions runner on the machine that runs Docker. Install Docker Engine and the Compose plugin, and add the runner labels `linux` and `docker` (alongside the default `self-hosted`). Keep the runner service online.
2. Start the Compose stack on that machine so SonarQube is available at port `9000`. Set `SONAR_HOST_URL` under **Settings → Secrets and variables → Actions → Variables** to `http://localhost:9000` (or the address reachable from the runner).
3. Create a SonarQube project with key `movie-app`, generate an analysis token, and add it as the Actions secret `SONAR_TOKEN`.
4. Create a Docker Hub access token and add `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` as Actions secrets. Create the repositories `movie-app-backend` and `movie-app-frontend` in that account if they are private or not yet created.
5. On pull requests and pushes, the `quality` job runs the existing pytest suite and uploads `test-results.xml`; it then sends source analysis to SonarQube. Pushes to `main` publish both images and trigger deployment. A failed quality job prevents publishing and deployment.

No Docker Hub or SonarQube credentials are stored in this repository, Dockerfiles, or Compose. The Compose MongoDB instance currently has no authentication configured, so it has no database credential to store. For local Compose use, copy `.env.example` to `.env`, set your Docker Hub username, and keep `.env` private; it is ignored by Git.

### Run or inspect the deployed version

The deployment keeps two backend and two frontend replicas. Nginx resolves the Compose service addresses dynamically, and the workflow updates each app service with `--wait` before updating the rest of the stack. This is the project's rolling deployment approach; health checks gate completion of each service update. To deploy manually, set `DOCKERHUB_USERNAME` and `APP_VERSION` to the desired image owner and immutable tag, then run the same `docker compose pull` and service update commands from the workflow. Check the active version with `docker compose images` and application status with `docker compose ps`.
