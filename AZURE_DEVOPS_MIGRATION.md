# Azure DevOps Migration Guide

Complete guide to migrate Blink Relay from GitHub to Azure DevOps, including CI/CD pipeline setup.

## Table of Contents

1. [Overview](#overview)
2. [Migration Strategy](#migration-strategy)
3. [Prerequisites](#prerequisites)
4. [Step 1: Set Up Azure DevOps Organization](#step-1-set-up-azure-devops-organization)
5. [Step 2: Create Azure DevOps Project](#step-2-create-azure-devops-project)
6. [Step 3: Migrate Code Repository](#step-3-migrate-code-repository)
7. [Step 4: Set Up CI/CD Pipeline](#step-4-set-up-cicd-pipeline)
8. [Step 5: Configure Build Pipeline](#step-5-configure-build-pipeline)
9. [Step 6: Configure Release Pipeline](#step-6-configure-release-pipeline)
10. [Step 7: Testing & Validation](#step-7-testing--validation)
11. [Rollback Plan](#rollback-plan)

---

## Overview

### Current State
- **Repository**: GitHub (jafarraza7-ops/blink_relay)
- **Branches**: main, blink_relay_local
- **CI/CD**: None (manual deployment)

### Target State
- **Repository**: Azure DevOps Git
- **Branches**: main, develop, feature branches
- **CI/CD**: Automated build, test, and deployment pipelines
- **Artifact Management**: Azure Container Registry for Docker images
- **Infrastructure**: Azure App Service deployment

### Benefits

✅ Integrated CI/CD with Azure DevOps Pipelines  
✅ Centralized project management with Azure Boards  
✅ Unified Azure ecosystem (AD, DevOps, App Service)  
✅ Better compliance and audit trails  
✅ Built-in secret management  
✅ Docker container support out of the box  
✅ Multi-stage pipeline (build → test → deploy)  

---

## Migration Strategy

### Phase 1: Setup (1 day)
- Create Azure DevOps organization
- Create project
- Set up repositories

### Phase 2: Code Migration (2 hours)
- Mirror repository from GitHub to Azure DevOps
- Preserve all history and branches
- Test access and permissions

### Phase 3: CI/CD Setup (1 day)
- Create build pipeline (CI)
- Create release pipeline (CD)
- Test pipeline on develop branch

### Phase 4: Validation (1 day)
- Run full pipeline end-to-end
- Test deployments
- Verify permissions and access

### Phase 5: Cutover (2 hours)
- Update main branch protection
- Update GitHub to read-only
- Deploy to production from Azure DevOps

---

## Prerequisites

### Azure Setup
- ✅ Azure subscription
- ✅ Azure DevOps organization (free tier available)
- ✅ Owner/Admin access to both

### GitHub Access
- ✅ Owner or admin access to GitHub repository
- ✅ SSH keys or personal access tokens configured

### Tools
- `git` command line
- Azure DevOps CLI (optional, for scripting)
- Docker (for container builds)

### Permissions Needed
- **Azure DevOps**: Project Collection Administrator
- **GitHub**: Admin access to repository
- **Azure**: Contributor role on resource group

---

## Step 1: Set Up Azure DevOps Organization

### Create Organization

1. **Go to** https://dev.azure.com
2. **Sign in** with your Microsoft account
3. **Create organization**:
   - Organization name: `BlinkCharging` (or your org name)
   - Region: Select closest region
   - Click **Create**

4. **Record organization URL**:
   ```
   https://dev.azure.com/BlinkCharging
   ```

### Create Project

1. **In your organization**, click **New project**

2. **Fill in project details**:
   ```
   Project name: Blink Relay
   Description: Internal tech request intake and management
   Visibility: Private
   Version control: Git
   Work item process: Scrum (or Agile)
   ```

3. **Click Create**

4. **Record project details**:
   ```
   Project URL: https://dev.azure.com/BlinkCharging/Blink%20Relay
   Project ID: {project-id}
   ```

### Set Up Permissions

1. **Go to Project Settings** → **Security**

2. **Add team members**:
   - Click **Add** under Members
   - Add users who need access
   - Assign roles:
     - **Admin/Lead**: Project Collection Administrators
     - **PM/Dev**: Contributors
     - **Viewers**: Readers

---

## Step 2: Create Azure DevOps Project

### Initialize Repositories

Azure DevOps creates a default repository. You can use this or create new ones.

**Option 1: Use Default Repository**
- Default repo name: `Blink Relay`
- Click **Clone** to get git URL
- Verify SSH/HTTPS access

**Option 2: Create Additional Repositories**
1. **Repos** → **Repositories** → **+ New repository**
2. Name: `blink-relay-main`
3. Type: Git
4. Initialize with README: No

### Configure Repository Settings

1. **Repo Settings** → **Policies**

2. **Set branch policies**:
   - **main branch**:
     - ✅ Require pull request reviews (minimum 2)
     - ✅ Require successful builds
     - ✅ Require code coverage
     - ✅ Dismiss stale pull requests

   - **develop branch**:
     - ✅ Require pull request reviews (minimum 1)
     - ✅ Require successful builds

---

## Step 3: Migrate Code Repository

### Option A: Mirror Repository (Recommended)

This preserves all history and tags.

```bash
# Clone GitHub repo with all history
git clone --mirror https://github.com/jafarraza7-ops/blink_relay.git blink_relay_mirror.git

# Push to Azure DevOps
cd blink_relay_mirror.git
git push --mirror https://dev.azure.com/BlinkCharging/Blink%20Relay/_git/blink-relay-main

# Verify
cd ..
rm -rf blink_relay_mirror.git

# Clone from Azure DevOps to verify
git clone https://dev.azure.com/BlinkCharging/Blink%20Relay/_git/blink-relay-main
cd blink-relay-main
git log --oneline | head -5  # Should show commit history
```

### Option B: Import Repository

1. **In Azure DevOps**, go to **Repos** → **Import repository**
2. **Clone URL**: `https://github.com/jafarraza7-ops/blink_relay.git`
3. **Click Import** (may take a few minutes)

### Verify Migration

```bash
# Check all branches exist
git branch -a

# Expected output:
# * main
#   remotes/origin/blink_relay_local
#   remotes/origin/develop
#   remotes/origin/main

# Check commit count matches GitHub
git log --oneline | wc -l

# Should match: git log on GitHub repo
```

### Push Updates

After migration, your local repo still points to GitHub. Update it:

```bash
# Remove GitHub remote
git remote remove origin

# Add Azure DevOps remote
git remote add origin https://dev.azure.com/BlinkCharging/Blink%20Relay/_git/blink-relay-main

# Verify
git remote -v
# Should show Azure DevOps URL

# Push all branches
git push --all
git push --tags
```

---

## Step 4: Set Up CI/CD Pipeline

### Create Build Pipeline (YAML)

File: `azure-pipelines.yml` (in repository root)

```yaml
trigger:
  branches:
    include:
      - main
      - develop
      - feature/*
    exclude:
      - blink_relay_local

pool:
  vmImage: 'ubuntu-latest'

variables:
  REGISTRY: 'blinkrelayacr.azurecr.io'
  IMAGE_NAME: 'blink-relay'
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '20.x'

stages:
  - stage: Build
    displayName: 'Build and Test'
    jobs:
      - job: Backend
        displayName: 'Backend Tests'
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '$(PYTHON_VERSION)'
            displayName: 'Use Python $(PYTHON_VERSION)'

          - script: |
              python -m pip install --upgrade pip
              pip install -r backend/backend/requirements.txt
              pip install pytest pytest-cov pytest-asyncio
            displayName: 'Install backend dependencies'

          - script: |
              cd backend/backend
              pytest tests/ -v --cov=app --cov-report=xml
            displayName: 'Run backend tests'

          - task: PublishCodeCoverageResults@1
            inputs:
              codeCoverageTool: Cobertura
              summaryFileLocation: 'backend/backend/coverage.xml'
            displayName: 'Publish code coverage'

      - job: Frontend
        displayName: 'Frontend Build'
        steps:
          - task: NodeTool@0
            inputs:
              versionSpec: '$(NODE_VERSION)'
            displayName: 'Use Node $(NODE_VERSION)'

          - script: |
              cd OneDrive_2_20-05-2026
              npm ci
            displayName: 'Install dependencies'

          - script: |
              cd OneDrive_2_20-05-2026
              npm run build
            displayName: 'Build frontend'

          - script: |
              cd OneDrive_2_20-05-2026
              npm run test:unit -- --run
            displayName: 'Run unit tests'
            continueOnError: true

          - task: PublishBuildArtifacts@1
            inputs:
              pathToPublish: 'OneDrive_2_20-05-2026/dist'
              artifactName: 'frontend-build'
            displayName: 'Publish frontend artifacts'

  - stage: Docker
    displayName: 'Build Docker Image'
    dependsOn: Build
    condition: succeeded()
    jobs:
      - job: BuildImage
        displayName: 'Build and Push Image'
        steps:
          - task: Docker@2
            displayName: 'Build image'
            inputs:
              command: 'build'
              Dockerfile: 'Dockerfile'
              tags: |
                $(REGISTRY)/$(IMAGE_NAME):$(Build.BuildId)
                $(REGISTRY)/$(IMAGE_NAME):latest
              arguments: |
                --build-arg PYTHON_VERSION=$(PYTHON_VERSION)
                --build-arg NODE_VERSION=$(NODE_VERSION)

          - task: Docker@2
            displayName: 'Push image to registry'
            inputs:
              command: 'push'
              containerRegistry: 'AzureContainerRegistry'
              repository: '$(IMAGE_NAME)'
              tags: |
                $(Build.BuildId)
                latest

```

### Create Pipeline in Azure DevOps

1. **Go to Pipelines** → **Create Pipeline**
2. **Select**: Azure Repos Git
3. **Select repository**: blink-relay-main
4. **Select**: Existing Azure Pipelines YAML file
5. **Path**: `/azure-pipelines.yml`
6. **Review and save**

---

## Step 5: Configure Build Pipeline

### Add Service Connections

**For Docker Registry:**

1. **Project Settings** → **Service connections**
2. **New service connection** → **Docker Registry**
3. **Configure**:
   ```
   Connection name: AzureContainerRegistry
   Registry type: Azure Container Registry
   Select subscription and registry
   ```

**For GitHub (for status checks):**

1. **New service connection** → **GitHub**
2. **Connect**: Authorize GitHub account
3. **Save**

### Configure Variables

1. **Pipelines** → **Library**
2. **Create variable group**:
   ```
   Name: BlueSky-Env
   Variables:
     AZURE_SUBSCRIPTION_ID: {subscription-id}
     AZURE_RESOURCE_GROUP: blink-relay-prod
     AZURE_APP_SERVICE: blink-relay-app
     REGISTRY_USERNAME: {acr-username}
   ```

3. **Link variable group** to pipeline (in azure-pipelines.yml):
   ```yaml
   variables:
     - group: BlueSky-Env
   ```

---

## Step 6: Configure Release Pipeline

### Create Release Pipeline

File: `azure-pipelines-release.yml`

```yaml
trigger: none  # Manual trigger only

pr: none

stages:
  - stage: DeployStaging
    displayName: 'Deploy to Staging'
    condition: eq(variables['Build.SourceBranch'], 'refs/heads/develop')
    jobs:
      - deployment: DeployApp
        displayName: 'Deploy to Azure App Service'
        environment: 'Staging'
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureWebApp@1
                  displayName: 'Deploy to App Service'
                  inputs:
                    azureSubscription: 'Azure-Subscription'
                    appType: 'webAppContainer'
                    appName: 'blink-relay-staging'
                    imageName: |
                      $(REGISTRY)/$(IMAGE_NAME):$(Build.BuildId)
                    containerRegistryType: 'Azure Container Registry'
                    registryUrl: 'https://$(REGISTRY)'

  - stage: DeployProduction
    displayName: 'Deploy to Production'
    condition: eq(variables['Build.SourceBranch'], 'refs/heads/main')
    jobs:
      - deployment: DeployApp
        displayName: 'Deploy to Production'
        environment: 'Production'
        strategy:
          runOnce:
            preDeploy:
              steps:
                - script: echo "Pre-deployment checks"
            deploy:
              steps:
                - task: AzureWebApp@1
                  displayName: 'Deploy to App Service'
                  inputs:
                    azureSubscription: 'Azure-Subscription'
                    appType: 'webAppContainer'
                    appName: 'blink-relay-prod'
                    imageName: |
                      $(REGISTRY)/$(IMAGE_NAME):$(Build.BuildId)
            postDeploy:
              steps:
                - script: echo "Post-deployment validation"
```

### Create Production Environment

1. **Pipelines** → **Environments**
2. **Create environment**:
   ```
   Name: Production
   Resource: Kubernetes (or Manual approval)
   ```

3. **Add approval**:
   - Approvers: [List of approvers]
   - Allow producer to approve: False

---

## Step 7: Testing & Validation

### Test Build Pipeline

1. **Create feature branch**:
   ```bash
   git checkout -b feature/test-pipeline
   git commit --allow-empty -m "Test: trigger pipeline"
   git push origin feature/test-pipeline
   ```

2. **Monitor build**:
   - Go to **Pipelines** → **Runs**
   - Watch build progress
   - Check test results

3. **Expected result**: ✅ Build succeeds, tests pass

### Test PR Workflow

1. **Create pull request** in Azure DevOps
2. **Verify**:
   - Build is triggered automatically
   - Code coverage is reported
   - PR can't merge until build passes

3. **Merge PR** to develop

### Test Staging Deployment

1. **Merge develop to staging branch** (if using)
2. **Verify** app deploys to staging
3. **Test in staging environment**
4. **Check logs**:
   ```bash
   az webapp log tail --resource-group blink-relay-staging --name blink-relay-staging-app
   ```

### Test Production Deployment

1. **Merge main branch** (or trigger manual deployment)
2. **Approval prompt** appears
3. **Click Approve**
4. **Monitor deployment**:
   - Pipelines UI shows progress
   - App Service shows new version
   - Health check passes

5. **Verify production**:
   ```bash
   curl https://blink-relay.blinkcharging.com/health
   # Should return {"status":"ok"}
   ```

---

## Rollback Plan

### If Deployment Fails

**Option 1: Revert Commit**
```bash
git revert HEAD
git push origin main
# Pipeline will deploy previous version
```

**Option 2: Manual Rollback in Azure**
1. **App Service** → **Deployment slots**
2. **Select previous deployment**
3. **Click Swap** to swap back

**Option 3: Redeploy Previous Build**
1. **Pipelines** → **Releases**
2. **Select previous successful release**
3. **Click Redeploy**

### Monitoring & Alerts

1. **Set up Application Insights alerts**:
   ```
   Alert on: Exception rate > 5/min
   Action: Send email + create incident
   ```

2. **Monitor deployment health**:
   - Response time
   - Error rate
   - CPU usage
   - Memory usage

3. **Check logs**:
   ```bash
   az monitor app-insights query \
     --app $APP_ID \
     --analytics-query "exceptions | count"
   ```

---

## Post-Migration

### Update Documentation

- [ ] Update README with new repo URL
- [ ] Update deployment instructions
- [ ] Document pipeline architecture
- [ ] Create runbooks for common issues

### Update CI/CD

- [ ] Configure branch policies
- [ ] Set up code owners (CODEOWNERS file)
- [ ] Configure build notifications
- [ ] Set up security scanning

### Update Development Workflow

- [ ] Team training on Azure DevOps
- [ ] Update git workflow docs
- [ ] Configure IDE integrations
- [ ] Set up local development guides

### Decommission GitHub

**After successful deployment:**

1. **Archive GitHub repository**:
   - Settings → Danger Zone → Archive repository
   - Mark as read-only

2. **Keep GitHub backup**:
   - Don't delete, just archive
   - Useful for reference

3. **Update team communication**:
   - Announce migration complete
   - Share new repository URL
   - Provide access instructions

---

## Troubleshooting

### Pipeline Fails to Trigger

**Check:**
- [ ] YAML syntax is valid
- [ ] Branch is in trigger list
- [ ] Service principal has access
- [ ] Webhooks are configured

**Solution:**
```bash
# Manually trigger pipeline
az pipelines run --name azure-pipelines.yml \
  --project "Blink Relay" \
  --org https://dev.azure.com/BlinkCharging
```

### Build Fails with Permission Error

**Error**: `Error: unauthorized: authentication required`

**Solution:**
1. Check service connection credentials
2. Verify registry access token is valid
3. Rotate credentials if needed

### Deployment Fails with "App Service not found"

**Error**: `ResourceNotFound: Could not find App Service`

**Solution:**
1. Verify App Service exists
2. Check app name spelling
3. Verify service principal has access
4. Check resource group is correct

### Performance Issues After Migration

**Symptoms**: Slow builds, timeouts

**Solutions:**
- Increase VM pool size
- Use self-hosted agents
- Optimize Docker image size
- Cache dependencies

---

## References

- [Azure DevOps Documentation](https://docs.microsoft.com/en-us/azure/devops/)
- [Azure Pipelines YAML Reference](https://docs.microsoft.com/en-us/azure/devops/pipelines/yaml-schema)
- [Git to Azure DevOps Migration](https://docs.microsoft.com/en-us/azure/devops/repos/git/import-git-repository)
- [Azure App Service Deployment](https://docs.microsoft.com/en-us/azure/app-service/)

---

## Checklist

### Pre-Migration
- [ ] Backup GitHub repository
- [ ] Inform team of migration plan
- [ ] Get stakeholder approval
- [ ] Prepare Azure resources

### Migration
- [ ] Create Azure DevOps organization
- [ ] Create project and repository
- [ ] Migrate code history
- [ ] Test repository access
- [ ] Set up branch policies

### CI/CD Setup
- [ ] Create build pipeline
- [ ] Create release pipeline
- [ ] Configure service connections
- [ ] Test end-to-end pipeline

### Validation
- [ ] Run full pipeline on develop
- [ ] Deploy to staging
- [ ] Verify staging deployment
- [ ] Deploy to production
- [ ] Verify production health

### Post-Migration
- [ ] Update documentation
- [ ] Train team
- [ ] Monitor for issues
- [ ] Archive GitHub

---

## Support

For questions or issues:
1. Check [Azure DevOps Docs](https://docs.microsoft.com/en-us/azure/devops/)
2. Review pipeline logs in Azure DevOps UI
3. Check Application Insights for runtime errors
4. Contact Azure support for infrastructure issues
