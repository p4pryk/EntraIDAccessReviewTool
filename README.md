
# Microsoft Entra ID Access Review Tool

**Automate creation and management of Access Reviews in Microsoft Entra ID (Azure AD)**

<img width="556" alt="image" src="https://github.com/user-attachments/assets/685a9485-889f-40cb-9a3f-59924c06f17a" />


---

## Table of Contents

- [Description](#description)  
- [Prerequisites](#prerequisites)  
- [Installation](#installation)  
- [Configuration](#configuration)  
- [Usage](#usage)  
- [Available Options](#available-options)  
- [Project Structure](#project-structure)  
- [Examples](#examples)  
- [Troubleshooting](#troubleshooting)  
- [Best Practices](#best-practices)  
- [Security Considerations](#security-considerations)  
- [Contributing](#contributing)  

---

## Description

This console application provides comprehensive management capabilities for Access Reviews of privileged roles in Microsoft Entra ID (formerly Azure AD). Access reviews help organizations efficiently validate and recertify user access, ensuring proper governance and compliance.

### Key Features

- **Role Management**  
  - List all available roles in your Entra ID tenant  
  - View detailed information about roles with assigned users  

- **Access Review Creation**  
  - Create one-time or recurring access reviews  
  - Configure flexible review schedules (weekly, monthly, quarterly, semi-annual)  
  - Target specific or all privileged roles  

- **Reviewer Management**  
  - Assign one or multiple reviewers to conduct access evaluations  
  - Configure self-review or manager-review options  

- **Review Administration**  
  - View all existing access reviews with detailed status  
  - Delete unnecessary or outdated reviews  
  - Track review progress and compliance  

> The application is built with a clear separation of concerns:  
> - API integration logic in [`entra_access_review.py`](entra_access_review.py)  
> - User interface and interaction handling in [`app.py`](app.py)  

---

## Prerequisites

- **Python Environment**  
  - Python 3.8 or higher  
  - pip package manager  

- **Python Packages**  
  - `requests` – For API communication with Microsoft Graph  
  - `colorama` – For enhanced terminal output formatting  

- **Microsoft Entra ID / Azure AD**  
  - Administrative access to create app registrations  
  - Privileges to manage access reviews  
  - A registered application with API permissions  

---

## Installation

### 1. Clone the Repository

```bash
git clone <repo-url>
cd EntraIDAccessReview
```

---

## Configuration

### App Registration Configuration

Before using this tool, you need to create an app registration in the Microsoft Entra admin center:

1. Navigate to **Microsoft Entra admin center > App registrations > New registration**  
2. Provide a name for your application (e.g., `EntraIDAccessReviewTool`)  
3. Select supported account types (Single tenant is recommended)  
4. Click **Register**  
5. Note down:  
   - Application (client) ID  
   - Directory (tenant) ID  
6. Under **Certificates & secrets**, create a new client secret and note its value  

### Required API Permissions

Add the following Microsoft Graph API permissions:

- `RoleManagement.ReadWrite.Directory`  
- `AccessReview.ReadWrite.All`  

Make sure to grant **admin consent** for these permissions.

### Application Configuration

Update authentication values in `app.py`:

```python
AZURE_TENANT_ID = "<Your tenant ID>"
AZURE_CLIENT_ID = "<Your client ID>"
AZURE_CLIENT_SECRET = "<Your client secret>"
```

Alternatively, set these as environment variables:

```powershell
# Windows (PowerShell)
$env:AZURE_TENANT_ID="<Your tenant ID>"
$env:AZURE_CLIENT_ID="<Your client ID>"
$env:AZURE_CLIENT_SECRET="<Your client secret>"
```

```bash
# macOS/Linux
export AZURE_TENANT_ID="<Your tenant ID>"
export AZURE_CLIENT_ID="<Your client ID>"
export AZURE_CLIENT_SECRET="<Your client secret>"
```

---

## Usage

To launch the application:

```bash
python app.py
```

After launching, you'll see an interactive menu that allows you to navigate through various access review management functions.

---

## Available Options

The tool provides the following options:

1. **List all roles**  
2. **List roles with assigned users**  
3. **Create access reviews for privileged roles**  
4. **Create access reviews for selected roles**  
5. **Create access reviews with custom schedule**  
6. **View or delete existing access reviews**  
7. **Set custom reviewer(s)**  
0. **Exit**

---

## Project Structure

| File | Description |
|------|-------------|
| `app.py` | Main CLI interface and menu |
| `entra_access_review.py` | Core logic and API communication |
| `__pycache__` | Compiled Python bytecode (auto-generated) |

### Key Functions

| File | Function | Description |
|------|----------|-------------|
| `entra_access_review.py` | `get_access_token()` | Authenticates with Graph API |
| `entra_access_review.py` | `get_directory_roles()` | Retrieves directory roles |
| `entra_access_review.py` | `get_role_members(role_id)` | Gets members for a role |
| `entra_access_review.py` | `create_access_review(...)` | Creates a new review |
| `entra_access_review.py` | `list_access_reviews()` | Lists all reviews |
| `entra_access_review.py` | `delete_access_review(review_id)` | Deletes a review |
| `app.py` | `display_menu()` | Shows the interactive menu |
| `app.py` | `handle_option(choice)` | Handles user selections |

---

