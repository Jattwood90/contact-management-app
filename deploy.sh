#!/bin/bash
set -e

echo "Deploying Contact Management System to Kubernetes"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    print_error "kind is not installed. Please install kind first."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi


print_status "Creating Kind cluster..."
if kind get clusters | grep -q "contact-mgmt"; then
    print_warning "Cluster 'contact-mgmt' already exists. Skipping cluster creation."
else
    kind create cluster --name contact-mgmt --config=k8s/kind-config.yaml
    print_success "Kind cluster created successfully"
fi

# Set kubectl context
kubectl config use-context kind-contact-mgmt

print_status "Building Docker images..."
docker build -t contact-app:latest .
docker build -t postgres-contact:latest ./db/
print_success "Docker images built successfully"

print_status "Loading images into Kind cluster..."
kind load docker-image contact-app:latest --name contact-mgmt
kind load docker-image postgres-contact:latest --name contact-mgmt
print_success "Images loaded into cluster"

print_status "Creating namespace..."
kubectl apply -f k8s/namespace.yaml
print_success "Namespace created"

print_status "Deploying with Kustomization..."
kubectl apply -k k8s/
print_success "All components deployed via Kustomization"

print_status "Waiting for database to be ready..."
if ! kubectl wait --for=condition=ready pod -l app=postgres-db -n contact-system --timeout=120s; then
    print_error "Database failed to become ready within 120 seconds. Checking logs..."
    echo "Pod status:"
    kubectl get pods -l app=postgres-db -n contact-system
    echo
    echo "Pod logs:"
    kubectl logs -l app=postgres-db -n contact-system --tail=50
    exit 1
fi
print_success "Database is ready"

print_status "Waiting for application to be ready..."
if ! kubectl wait --for=condition=ready pod -l app=contact-app -n contact-system --timeout=120s; then
    print_error "Application failed to become ready within 120 seconds. Checking logs..."
    echo "Pod status:"
    kubectl get pods -l app=contact-app -n contact-system
    echo
    echo "Pod logs:"
    kubectl logs -l app=contact-app -n contact-system --tail=50
    exit 1
fi
print_success "Application is ready"

echo
print_success "Deployment completed successfully!"
echo "=============================================="


echo "1. Access Database (PostgreSQL):"
echo "   kubectl port-forward -n contact-system service/postgres-service 5432:5432 &"
echo "   psql -h localhost -p 5432 -U postgres -d postgres"
echo "   Password: secret-password"
echo

echo "2. Access Web Application:"
echo "   kubectl port-forward -n contact-system service/contact-app-service 8080:3000 &"
echo "   Open: http://localhost:8080"
echo

echo "  Monitoring Commands:"
echo "   kubectl get all -n contact-system"
echo "   kubectl logs -f deployment/contact-app -n contact-system"
echo "   kubectl logs -f deployment/postgres-db -n contact-system"
echo

echo "🧹 Cleanup:"
echo "   kind delete cluster --name contact-mgmt"
echo

# Check if user wants to start port forwarding immediately
read -p "Start port forwarding now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Starting port forwarding..."
    
    # Kill any existing port forwards
    pkill -f "kubectl port-forward" || true
    
    # Start database port forward
    kubectl port-forward -n contact-system service/postgres-service 5432:5432 &
    DB_PF_PID=$!
    
    # Start application port forward
    kubectl port-forward -n contact-system service/contact-app-service 8080:3000 &
    APP_PF_PID=$!
    
    print_success "Port forwarding started!"
    echo "  • Database: localhost:5432"
    echo "  • Web App: http://localhost:8080"
    echo
    echo "Press Ctrl+C to stop port forwarding and exit"
    
    # Wait for interrupt
    trap 'kill $DB_PF_PID $APP_PF_PID 2>/dev/null; exit' INT
    wait
fi