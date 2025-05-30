import os, sys, requests, datetime, json, re

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
ROLES_URL = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions"
REVIEWS_URL = "https://graph.microsoft.com/v1.0/identityGovernance/accessReviews/definitions"

# Lista ról uprzywilejowanych (identyfikatory zgodne z Entra ID)
PRIVILEGED_ROLES = [
    "62e90394-69f5-4237-9190-012177145e10",  # Global Administrator
    "194ae4cb-b126-40b2-bd5b-6091b380977d",  # Security Administrator
    "e8611ab8-c189-46e8-94e1-60213ab1f814",  # Privileged Role Administrator
    "7be44c8a-adaf-4e2a-84d6-ab2649e08a13",  # Privileged Authentication Administrator
    "b1be1c3e-b65d-4f19-8427-f6fa0d97feb9",  # Conditional Access Administrator
    "9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3",  # Application Administrator
    "158c047a-c907-4556-b7ef-446551a6b5f7",  # Cloud Application Administrator
    "7698a772-787b-4ac8-901f-60d6b08affd2",  # Cloud Device Administrator
    "17315797-102d-40b4-93e0-432062caca18",  # Compliance Administrator
    "fe930be7-5e62-47db-91af-98c3a49a38b1",  # User Administrator
    "3a2c62db-5318-420d-8d74-23affee5d9d5",  # Intune Administrator
    "0526716b-113d-4c15-b2c8-68e3c22b9f80",  # Authentication Policy Administrator
    "c4e39bd9-1100-46d3-8c65-fb160da0071f",  # Authentication Administrator
    "8ac3fc64-6eca-42ea-9e69-59f4c7b60eb2",  # Hybrid Identity Administrator
    "5f2222b1-57c3-48ba-8ad5-d4759f1fde6f",  # Security Operator
    "cf1c38e5-3621-4004-a7cb-879624dced7c",  # Application Developer
    "9c6df0f2-1e7c-4dc3-b195-66dfbd24aa8f",  # Attack Payload Author
    "58a13ea3-c632-46ae-9ee0-9c0d43cd7f3d",  # Attribute Assignment Administrator
    "ecb2c6bf-0ab6-418e-bd87-7986f8d63bbe",  # Attribute Provisioning Administrator
    "25a516ed-2fa0-40ea-a2d0-12923a21473a",  # Authentication Extensibility Administrator
    "e3973bdf-4987-49ae-837a-ba8e231c7286",  # Azure DevOps Administrator
    "aaf43236-0c0d-4d5f-883a-6955382ac081",  # B2C IEF Keyset Administrator
    "3edaf663-341e-4475-9f94-5c398ef6c070",  # B2C IEF Policy Administrator
    "be2f45a1-457d-42af-a067-6ec1fa63bc45",  # External Identity Provider Administrator
    "ac434307-12b9-4fa1-a708-88bf58caabc1",  # Global Secure Access Administrator
    "59d46f88-662b-457b-bceb-5c3809e5908f",  # Lifecycle Workflows Administrator
    "11451d60-acb2-45eb-a7d6-43d0f0125c13",  # Windows 365 Administrator
]

def get_token(tenant_id, client_id, client_secret):
    """Pobiera token dostępu do Microsoft Graph API"""
    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Brakujące dane uwierzytelniania (tenant, client_id, client_secret)")
    
    data = {
        "client_id": client_id,
        "scope": GRAPH_SCOPE,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    r = requests.post(TOKEN_URL.format(tenant=tenant_id), data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def get_roles(token):
    """Pobiera listę ról z Microsoft Graph API"""
    hdr = {"Authorization": f"Bearer {token}"}
    r = requests.get(ROLES_URL, headers=hdr)
    r.raise_for_status()
    return r.json().get("value", [])

def filter_built_in_roles(roles):
    """Filtruje listę ról, pozostawiając tylko wbudowane role"""
    return [role for role in roles if role.get('isBuiltIn', False)]

def create_access_review(token, role, reviewer_ids=None):
    """Tworzy Access Review dla wybranej roli"""
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    now_dt = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    now = now_dt.isoformat().replace("+00:00", "Z")
    start_date = now.split("T")[0]  # Tylko data bez czasu
    
    body = {
        "displayName": f"Review: {role['displayName']}",
        "descriptionForAdmins": f"Access review for {role['displayName']} role",
        "descriptionForReviewers": f"Please review access for {role['displayName']} role",
        "scope": {
            "@odata.type": "#microsoft.graph.principalResourceMembershipsScope",
            "principalScopes": [
                {
                    "@odata.type": "#microsoft.graph.accessReviewQueryScope",
                    "query": "/users",
                    "queryType": "MicrosoftGraph"
                },
                {
                    "@odata.type": "#microsoft.graph.accessReviewQueryScope",
                    "query": "/groups",
                    "queryType": "MicrosoftGraph"
                }
            ],
            "resourceScopes": [
                {
                    "@odata.type": "#microsoft.graph.accessReviewQueryScope",
                    "query": f"/roleManagement/directory/roleDefinitions/{role['id']}",
                    "queryType": "MicrosoftGraph"
                }
            ]
        },
        "settings": {
            "mailNotificationsEnabled": True,
            "reminderNotificationsEnabled": True,
            "justificationRequiredOnApproval": True,
            "defaultDecisionEnabled": False,
            "defaultDecision": "None",
            "instanceDurationInDays": 30,
            "autoApplyDecisionsEnabled": True,
            "recommendationsEnabled": True,
            "recurrence": {
                "pattern": {
                    "type": "absoluteMonthly",
                    "interval": 6,
                    "dayOfMonth": 1,
                },
                "range": {
                    "type": "noEnd",
                    "startDate": start_date
                }
            }
        }
    }
    
    # Add reviewers section if reviewer_ids are provided
    if reviewer_ids:
        body["reviewers"] = []
        
        # Convert single ID to list if needed
        if isinstance(reviewer_ids, str):
            reviewer_ids = [reviewer_ids]
            
        for rid in reviewer_ids:
            body["reviewers"].append({
                "query": f"/users/{rid}",
                "queryType": "MicrosoftGraph"
            })
    
    r = requests.post(REVIEWS_URL, headers=hdr, json=body)
    result = {
        "role_name": role["displayName"],
        "role_id": role["id"],
        "success": r.ok,
        "status_code": r.status_code
    }
    
    if not r.ok:
        try:
            result["error"] = r.json()
        except ValueError:
            result["error"] = r.text
    
    return result

def get_users_for_role(token, role_id):
    """Pobiera listę użytkowników przypisanych do danej roli"""
    url = f"https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments?$filter=roleDefinitionId eq '{role_id}'"
    hdr = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=hdr)
    r.raise_for_status()
    
    assignments = r.json().get("value", [])
    principals = []
    
    for assignment in assignments:
        principal_id = assignment.get("principalId")
        if principal_id:
            user_url = f"https://graph.microsoft.com/v1.0/directoryObjects/{principal_id}"
            r_user = requests.get(user_url, headers=hdr)
            if r_user.ok:
                obj = r_user.json()
                obj_type = obj.get("@odata.type", "")
                if "#microsoft.graph.user" in obj_type:
                    principals.append({
                        "id": principal_id,
                        "type": "user",
                        "displayName": obj.get("displayName", "Unknown")
                    })
                elif "#microsoft.graph.group" in obj_type:
                    principals.append({
                        "id": principal_id,
                        "type": "group",
                        "displayName": obj.get("displayName", "Unknown Group")
                    })
    
    return principals

def list_access_reviews(token):
    """
    List all access reviews in the tenant
    
    Args:
        token: Authentication token
        
    Returns:
        List of access reviews
    """
    url = "https://graph.microsoft.com/v1.0/identityGovernance/accessReviews/definitions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        print(f"Error fetching access reviews: {response.status_code}")
        print(response.text)
        return []

def get_access_review_status(token, review_id):
    """
    Get status of a specific access review
    
    Args:
        token: Authentication token
        review_id: ID of the access review
        
    Returns:
        Dictionary with review status details
    """
    url = f"https://graph.microsoft.com/v1.0/identityGovernance/accessReviews/definitions/{review_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        review_details = response.json()
        
        # Get instances (actual review cycles) for this definition
        instances_url = f"https://graph.microsoft.com/v1.0/identityGovernance/accessReviews/definitions/{review_id}/instances"
        instances_response = requests.get(instances_url, headers=headers)
        
        if instances_response.status_code == 200:
            review_details['instances'] = instances_response.json().get('value', [])
        
        return review_details
    else:
        return {
            "success": False,
            "status_code": response.status_code,
            "error": response.json() if response.text else f"HTTP Error {response.status_code}"
        }

def delete_access_review(token, review_id):
    """
    Delete an access review
    
    Args:
        token: Authentication token
        review_id: ID of the access review to delete
        
    Returns:
        Dictionary with operation result
    """
    url = f"https://graph.microsoft.com/v1.0/identityGovernance/accessReviews/definitions/{review_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.delete(url, headers=headers)
    
    return {
        "success": response.status_code == 204,
        "status_code": response.status_code,
        "error": response.json() if response.text else None
    }

def create_access_review_with_schedule(token, role, reviewer_ids=None, frequency="quarterly"):
    """
    Create access review with configurable schedule
    
    Args:
        token: Authentication token
        role: Dictionary with role details
        reviewer_ids: ID or list of IDs of reviewers
        frequency: one of "weekly", "monthly", "quarterly", "halfyearly"
        
    Returns:
        Dictionary with operation result
    """
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Check if role ID is properly formatted
    role_id = role.get("id")
    if not role_id or not isinstance(role_id, str) or not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', role_id, re.I):
        return {
            "role_name": role.get("displayName", "Unknown Role"),
            "role_id": role_id,
            "success": False,
            "status_code": 400,
            "error": f"Invalid role ID format: {role_id}. Expected GUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        }
    
    # Generate payload using prepare_review_with_schedule_payload
    body = prepare_review_with_schedule_payload(role, reviewer_ids, frequency)
    
    r = requests.post(REVIEWS_URL, headers=hdr, json=body)
    result = {
        "role_name": role["displayName"],
        "role_id": role["id"],
        "success": r.ok,
        "status_code": r.status_code
    }
    
    if not r.ok:
        try:
            result["error"] = r.json()
        except ValueError:
            result["error"] = r.text
    
    return result

def prepare_review_with_schedule_payload(role, reviewer_ids, frequency="quarterly"):
    """
    Prepare payload for access review with schedule without sending it
    
    Args:
        role: Dictionary with role details
        reviewer_ids: ID or list of IDs of reviewers
        frequency: one of "weekly", "monthly", "quarterly", "halfyearly"
        
    Returns:
        Payload dictionary ready to be sent
    """
    # Validate role_id format
    role_id = role.get("id")
    if not role_id or not isinstance(role_id, str) or not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', role_id, re.I):
        raise ValueError(f"Invalid role ID format: {role_id}. Expected GUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    
    # Map frequency to recurrence pattern
    frequency_settings = {
        "weekly": {
            "type": "weekly",
            "interval": 1
        },
        "monthly": {
            "type": "absoluteMonthly",
            "interval": 1,
            "dayOfMonth": 1
        },
        "quarterly": {
            "type": "absoluteMonthly",
            "interval": 3,
            "dayOfMonth": 1
        },
        "halfyearly": {
            "type": "absoluteMonthly",
            "interval": 6,
            "dayOfMonth": 1
        }
    }
    
    # Use default if frequency not found
    freq_pattern = frequency_settings.get(frequency.lower(), frequency_settings["quarterly"])
    
    # Format date exactly like in create_access_review
    now_dt = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    now = now_dt.isoformat().replace("+00:00", "Z")
    start_date = now.split("T")[0]  # Tylko data bez czasu
    
    # Build payload using the exact same structure as create_access_review
    payload = {
        "displayName": f"Review: {role['displayName']}",
        "descriptionForAdmins": f"Access review for {role['displayName']} role",
        "descriptionForReviewers": f"Please review access for {role['displayName']} role",
        "scope": {
            "@odata.type": "#microsoft.graph.principalResourceMembershipsScope",
            "principalScopes": [
                {
                    "@odata.type": "#microsoft.graph.accessReviewQueryScope",
                    "query": "/users",
                    "queryType": "MicrosoftGraph"
                },
                {
                    "@odata.type": "#microsoft.graph.accessReviewQueryScope",
                    "query": "/groups",
                    "queryType": "MicrosoftGraph"
                }
            ],
            "resourceScopes": [
                {
                    "@odata.type": "#microsoft.graph.accessReviewQueryScope",
                    "query": f"/roleManagement/directory/roleDefinitions/{role_id}",
                    "queryType": "MicrosoftGraph"
                }
            ]
        },
        "settings": {
            "mailNotificationsEnabled": True,
            "reminderNotificationsEnabled": True,
            "justificationRequiredOnApproval": True,
            "defaultDecisionEnabled": False,
            "defaultDecision": "None",
            "instanceDurationInDays": 30,
            "autoApplyDecisionsEnabled": True,
            "recommendationsEnabled": True,
            "recurrence": {
                "pattern": freq_pattern,
                "range": {
                    "type": "noEnd",
                    "startDate": start_date
                }
            }
        }
    }
    
    # Add reviewers section - obsługa zarówno pojedynczego ID jak i listy
    if reviewer_ids:
        payload["reviewers"] = []
        
        # Konwersja pojedynczego ID do listy jeśli potrzeba
        if isinstance(reviewer_ids, str):
            reviewer_ids = [reviewer_ids]
            
        for rid in reviewer_ids:
            payload["reviewers"].append({
                "query": f"/users/{rid}",
                "queryType": "MicrosoftGraph"
            })
    
    return payload

def send_review_request(token, payload):
    """
    Send prepared review request payload
    
    Args:
        token: Authentication token
        payload: Prepared payload
        
    Returns:
        Dictionary with operation result
    """
    url = "https://graph.microsoft.com/v1.0/identityGovernance/accessReviews/definitions"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 201:
            return {
                "success": True,
                "status_code": response.status_code
            }
        else:
            error_data = None
            try:
                error_data = response.json()
            except:
                error_data = response.text if response.text else f"HTTP Error {response.status_code}"
                
            return {
                "success": False,
                "status_code": response.status_code,
                "error": error_data
            }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "error": str(e)
        }
