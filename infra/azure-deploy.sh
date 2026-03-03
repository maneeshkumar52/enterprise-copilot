#!/bin/bash
set -e
echo "Deploying Enterprise Knowledge Copilot..."
az group create --name rg-enterprise-copilot --location uksouth
az containerapp create --name enterprise-copilot --resource-group rg-enterprise-copilot --image python:3.11-slim --target-port 8000 --ingress external
echo "Done!"
