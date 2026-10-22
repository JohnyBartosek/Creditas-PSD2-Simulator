# Configuration Files

This directory contains configuration files for the project.

## Entra ID Configuration

### Setup

1. Copy `entra_config.json.template` to `entra_config.json`:
   ```bash
   cp entra_config.json.template entra_config.json
   ```

2. Edit `entra_config.json` and fill in your actual credentials:
   ```json
   {
     "tenant_id": "your-tenant-id",
     "client_id": "your-client-id",
     "client_secret": "your-client-secret",
     "component_client_id": "your-component-client-id",
     "employee_username": "your-username@creditas.cz",
     "employee_password": "your-password"
   }
   ```

### Security Note

⚠️ **Important**: The `entra_config.json` file contains sensitive credentials. 
- Do NOT commit this file to version control
- Add it to `.gitignore` if not already present
- Keep it secure and only share with authorized team members

### Usage in Python Scripts

Python scripts automatically load credentials from this file:
- `Helpers/employee_token_retriever.py`
- `Helpers/sms_otp_helper.py`

### Usage in TypeScript Scripts

TypeScript scripts automatically load credentials from this file:
- `Templates/TypeScript/helpers/smsOtpHelper.ts`
- `Templates/TypeScript/obo-slp-tokens.spec.ts`

The TypeScript helper `entraConfig.ts` loads the configuration at runtime.

### Usage in Bruno

For Bruno API client, set environment variables in your Bruno collection:

1. Open your Bruno collection
2. Go to Environment settings
3. Add the following variables (values from `entra_config.json`):
   - `entra_tenant_id`
   - `entra_client_id`
   - `entra_client_secret`
   - `entra_component_client_id`
   - `entra_employee_username`
   - `entra_employee_password`

The Bruno request files will automatically use these environment variables.

