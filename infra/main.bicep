// =============================================================================
// Fishadoo – Azure Infrastructure
// =============================================================================
// Deploys:
//   • Storage Account  (Function App state + RandomStrings table)
//   • Log Analytics Workspace + Application Insights
//   • App Service Plan (Consumption Y1)
//   • Function App (Python 3.12, system-assigned managed identity)
//   • Role assignment: Function App MI → Storage Table Data Contributor
//
// The Function App uses its managed identity to access Table Storage –
// no connection strings are stored in code or app settings.
// =============================================================================

@description('Base name used to derive all resource names. 3-12 alphanumeric characters.')
@minLength(3)
@maxLength(12)
param baseName string = 'fishadoo'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('CRON schedule for the timer trigger (6-field, seconds first). Matches config.json schedule.')
param schedule string = '0 */10 * * * *'

@description('Name of the Azure Storage table to write to.')
param tableName string = 'RandomStrings'

@description('Python version for the Function App worker.')
@allowed(['3.11', '3.12'])
param pythonVersion string = '3.12'

// ---------------------------------------------------------------------------
// Derived names
// ---------------------------------------------------------------------------
var storageAccountName = '${toLower(baseName)}${uniqueString(resourceGroup().id)}'
var logAnalyticsName   = '${baseName}-logs'
var appInsightsName    = '${baseName}-ai'
var hostingPlanName    = '${baseName}-plan'
var functionAppName    = '${baseName}-func'

// ---------------------------------------------------------------------------
// Storage Account
// ---------------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: 'Allow' // Tighten to 'Deny' + VNet rules as the project grows.
    }
  }
}

// ---------------------------------------------------------------------------
// Log Analytics Workspace
// ---------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Application Insights
// ---------------------------------------------------------------------------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------------------------------------------------------------------------
// App Service Plan (Consumption – serverless)
// ---------------------------------------------------------------------------
resource hostingPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: hostingPlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {}
}

// ---------------------------------------------------------------------------
// Function App
// ---------------------------------------------------------------------------
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: hostingPlan.id
    siteConfig: {
      pythonVersion: pythonVersion
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccount.name
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'TABLE_NAME'
          value: tableName
        }
        {
          name: 'SCHEDULE'
          value: schedule
        }
        {
          name: 'TABLE_ACCOUNT_NAME'
          value: storageAccount.name
        }
        // TABLE_CONNECTION_STRING is intentionally absent – the Function App
        // authenticates to Table Storage via its system-assigned managed identity
        // (Storage Table Data Contributor role assigned below).  No secrets are
        // stored in app settings.
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
    }
    httpsOnly: true
  }
}

// ---------------------------------------------------------------------------
// RBAC – grant the Function App's managed identity access to Table Storage
// ---------------------------------------------------------------------------
// Role: Storage Table Data Contributor
// https://learn.microsoft.com/azure/role-based-access-control/built-in-roles#storage-table-data-contributor
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      storageTableDataContributorRoleId
    )
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output functionAppName string = functionApp.name
output storageAccountName string = storageAccount.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
