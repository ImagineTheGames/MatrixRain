# Publish Matrix Screensaver via Microsoft Store Developer CLI

Use the **Microsoft Store Developer CLI** (`msstore`) to publish from the command line.

## Prerequisites

1. **Partner Center**
   - [Register as a Windows app developer](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/partner-center-developer-account) (one-time fee).
   - [Associate a Microsoft Entra ID (Azure AD) tenant](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/associate-existing-azure-ad-tenant-with-partner-center-account) with your Partner Center account.

2. **First submission (one-time, in the browser)**
   - In [Partner Center](https://partner.microsoft.com/dashboard), create a **new product** → **Windows app** → **Store installer (EXE/MSI)**.
   - Fill in the listing (name: **Matrix Screensaver**, description, screenshots, icons from `store/`).
   - Create and complete **one submission** (upload the EXE or a zip of the app, set pricing to Free, etc.) so the product exists and has a **Product ID**.

After that, you can use the CLI for **updates** (new versions).

## Install the CLI

```powershell
# .NET 8 Desktop Runtime (required)
winget install Microsoft.DotNet.DesktopRuntime.8

# Microsoft Store Developer CLI
winget install "Microsoft Store Developer CLI"
```

## Configure the CLI (one-time)

Run:

```powershell
msstore
```

Sign in with **Microsoft Entra ID** (work/school) credentials linked to your Partner Center account — **not** a personal Microsoft account (MSA).

To reconfigure (e.g. different tenant/seller):

```powershell
msstore reconfigure
```

Optional: use client secret for scripts/CI:

```powershell
msstore reconfigure --tenantId <TENANT_ID> --sellerId <SELLER_ID> --clientId <CLIENT_ID> --clientSecret <CLIENT_SECRET>
```

## Get your Product ID

In Partner Center: open your app → **Product identity** → **Product ID** (e.g. `9N12345678AB`). You need this for all CLI commands.

## Build and publish from the repo

1. **Bump version** in `version.py` (see `.cursor/rules/version-and-build.mdc`).

2. **Build** (cleans and produces `dist\Matrix Screensaver\`):

   ```powershell
   cd X:\MyApps\MatrixRain
   .\build\build.ps1
   ```

3. **Publish via CLI** (run from repo root):

   ```powershell
   .\build\publish-store.ps1 -ProductId "9NXXXXXXXX"
   ```

   Replace `9NXXXXXXXX` with your app’s Product ID.

The script will:
- Run the build if needed (or use `-SkipBuild` if already built).
- Create `dist\MatrixScreensaver-<version>.zip` for upload.
- Run `msstore submission status <ProductId>`.
- Run `msstore submission publish <ProductId>` to submit for certification.

**Note:** For EXE/Store installer apps, you may need to **upload the new build** in Partner Center (Dashboard → your app → Submission → Update the installer) with the generated zip or the contents of `dist\Matrix Screensaver\`, then use the CLI to **publish** that submission. The script runs `msstore submission publish`; if your submission doesn’t yet include the new package, do the upload in the Partner Center UI first, then run the script.

## Useful CLI commands

| Command | Description |
|--------|--------------|
| `msstore info` | Show current CLI configuration. |
| `msstore submission status <ProductId>` | Status of the current submission. |
| `msstore submission get <ProductId>` | Get submission metadata. |
| `msstore submission publish <ProductId>` | Publish the submission (send for certification). |
| `msstore submission poll <ProductId>` | Poll until submission finishes. |

## Limits

- **Free products only:** App update operations via the CLI are currently supported for **free** products. Paid products will be supported later.
- **Entra ID required:** You must use an Entra ID (Azure AD) account linked to Partner Center, not a personal Microsoft account.
