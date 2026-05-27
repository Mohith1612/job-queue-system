# Kubernetes (kind) setup

Run the backend on a local single-node Kubernetes cluster using [kind](https://kind.sigs.k8s.io/).

> **Heads up:** this is a learning setup, not a production deployment. It runs one replica of everything on a single node, Postgres data is ephemeral (`emptyDir`), and the dev DB password is checked into `secret.yaml`. The frontend is not included — run it locally with `npm run dev` or via the existing `docker-compose.yml`.

## What's in here

| File | What it is |
|---|---|
| `cluster/kind-config.yaml` | Single-node kind cluster, exposes nodePort 30080 to the host (kept out of the main dir so `kubectl apply -f k8s/` doesn't try to apply it) |
| `00-namespace.yaml` | `jobqueue` namespace — `00-` prefix makes it sort first so a fresh `kubectl apply` doesn't race namespaced resources |
| `configmap.yaml` | Non-secret env vars (`LOG_LEVEL`, `REDIS_URL`, etc.) |
| `secret.yaml` | Dev-only `DATABASE_URL` and `POSTGRES_PASSWORD` |
| `postgres.yaml` | Postgres Deployment + ClusterIP Service (`emptyDir` storage) |
| `redis.yaml` | Redis Deployment + ClusterIP Service |
| `api.yaml` | FastAPI Deployment + NodePort Service (host port 30080) |
| `worker.yaml` | Worker Deployment (no Service — outbound only) |

## Concepts, quickly

- **Deployment** — "keep N copies of this pod running." Restart a pod and it comes back.
- **Service** — a stable virtual IP + DNS name that load-balances across the pods behind it. The worker connects to `redis://redis:6379` and `redis` resolves to the Redis Service inside the `jobqueue` namespace. Pods don't need to know each other's IPs.
- **ClusterIP** vs **NodePort** — ClusterIP is only reachable inside the cluster (Postgres, Redis). NodePort opens a fixed port on the node so you can hit it from your laptop (the API on `:30080`).
- **ConfigMap / Secret** — key-value config injected as env vars. Secret is base64-encoded; not encrypted, just less likely to end up in a screenshot.
- **Namespace** — a folder to group resources so they don't collide with anything else on the cluster.

## Running it

Prereqs: [Docker](https://docs.docker.com/get-docker/), [`kind`](https://kind.sigs.k8s.io/docs/user/quick-start/#installation), [`kubectl`](https://kubernetes.io/docs/tasks/tools/).

```bash
# 1. Create the cluster
kind create cluster --config k8s/cluster/kind-config.yaml --name jobqueue

# 2. Build the images locally
docker build -f Dockerfile.api    -t jobqueue-api:dev    .
docker build -f Dockerfile.worker -t jobqueue-worker:dev .

# 3. Load them into the kind node (no registry needed)
kind load docker-image jobqueue-api:dev jobqueue-worker:dev

# 4. Apply everything (the 00- prefix on namespace.yaml makes it apply first)
kubectl apply -f k8s/

# 5. Watch the pods come up
kubectl get pods -n jobqueue -w

# 6. Hit the API
curl http://localhost:30080/health

# 7. Submit a job and watch the worker pick it up
curl -X POST http://localhost:30080/jobs \
  -H 'Content-Type: application/json' \
  -d '{"type":"email_send","payload":{"to":"x@example.com"},"priority":"high"}'

kubectl logs -n jobqueue deploy/worker -f
```

## Teardown

```bash
kind delete cluster --name jobqueue
```

## Iterating on code

After changing app code:

```bash
docker build -f Dockerfile.api -t jobqueue-api:dev .
kind load docker-image jobqueue-api:dev --name jobqueue
kubectl rollout restart deploy/api -n jobqueue
```

## Notes

- Postgres data resets when the pod restarts. The API runs `alembic upgrade head` on startup so the schema comes back automatically.
- If pods get stuck in `ContainerCreating`, it's usually the image not being loaded yet — re-run `kind load docker-image …`.
- `imagePullPolicy: IfNotPresent` is important: without it, K8s tries to pull from a registry and fails because these images only exist locally.
