# Create the cluster
kind create cluster --config kind-config.yaml

# Verify the cluster
kubectl cluster-info
kubectl get nodes

# Use the cluster
kubectl config use-context kind-contact-mgmt

# Clean up when done
kind delete cluster --name contact-mgmt

# Secrets
created by kustomize during ./deploy.sh
