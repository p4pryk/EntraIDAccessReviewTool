import os
import sys
import json
import colorama
from colorama import Fore, Style
import re
from entra_access_review import (
    get_token, get_roles, filter_built_in_roles, 
    create_access_review, get_users_for_role, PRIVILEGED_ROLES
)
import requests

# Initialize colorama for cross-platform colored terminal output
colorama.init(autoreset=True)

# Hard-coded configuration
AZURE_TENANT_ID = "#"
AZURE_CLIENT_ID = "#"
AZURE_CLIENT_SECRET = "#"
REVIEWER_ID = "#"

def display_welcome_banner():
    """Display a welcome banner when the application starts"""
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║             MICROSOFT ENTRA ID ACCESS REVIEW TOOL         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.BLUE}This tool helps you manage access reviews in Microsoft Entra ID.
It allows you to automate the creation and management of access reviews
for roles in your organization to maintain security compliance.

{Fore.YELLOW}Tool capabilities:{Style.RESET_ALL}
• List all Entra ID roles with privileged role identification
• View user and group assignments for each role
• Create scheduled access reviews for privileged roles
• Generate custom access reviews for selected roles
• Configure review schedules (weekly, monthly, quarterly, or half-yearly)
• Assign single or multiple reviewers to access reviews
• View and manage existing access reviews

{Fore.GREEN}Default settings:{Style.RESET_ALL}
• Review schedule: Half-yearly (every 6 months)
• Reviewer: Self-review (users review their own access)

{Fore.GREEN}Access reviews help ensure that users have appropriate access to resources
and can be scheduled to run automatically at defined intervals.{Style.RESET_ALL}

{Fore.RED}Note: This tool requires an app registration with Microsoft Graph API
permissions in your Entra ID tenant.{Style.RESET_ALL}
"""
    print(banner)

def authenticate():
    """Authenticate with Azure and return the token"""
    try:
        print(f"{Fore.BLUE}Authenticating with Azure...")
        token = get_token(
            AZURE_TENANT_ID,
            AZURE_CLIENT_ID,
            AZURE_CLIENT_SECRET
        )
        print(f"{Fore.GREEN}Authentication successful.")
        return token
    except Exception as e:
        print(f"{Fore.RED}Authentication failed: {str(e)}")
        sys.exit(1)

def list_roles(detailed=False):
    """List all roles in Entra ID and return them
    
    Args:
        detailed: If True, show detailed information for each role (ignored in this version)
        
    Returns:
        List of roles with is_privileged flag set
    """
    token = authenticate()
    
    print(f"{Fore.BLUE}Fetching roles from Entra ID...")
    all_roles = get_roles(token)
    built_in_roles = filter_built_in_roles(all_roles)
    
    # Mark privileged roles
    privileged_count = 0
    for role in built_in_roles:
        role['is_privileged'] = role['id'] in PRIVILEGED_ROLES
        if role['is_privileged']:
            privileged_count += 1
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== ENTRA ID ROLES ===")
    print(f"Total roles: {len(all_roles)}")
    print(f"Built-in roles: {len(built_in_roles)}")
    print(f"Privileged roles: {privileged_count}")
    
    # Sort roles - privileged first, then alphabetically
    built_in_roles.sort(key=lambda r: (not r['is_privileged'], r['displayName'].lower()))
    
    # Print all roles with numbers for selection
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Available roles:")
    for i, role in enumerate(built_in_roles, 1):
        if role['is_privileged']:
            print(f"{i}. {Fore.RED}{Style.BRIGHT}[PRIVILEGED] {role['displayName']} ({role['id']}){Style.RESET_ALL}")
        else:
            print(f"{i}. {role['displayName']} ({role['id']})")
    
    return built_in_roles

def list_roles_with_users():
    """List roles with assigned users"""
    token = authenticate()
    
    print(f"{Fore.BLUE}Fetching roles from Entra ID...")
    all_roles = get_roles(token)
    built_in_roles = filter_built_in_roles(all_roles)
    
    # Mark privileged roles
    for role in built_in_roles:
        role['is_privileged'] = role['id'] in PRIVILEGED_ROLES
    
    roles_with_users = []
    print(f"{Fore.BLUE}Checking user assignments for each role...")
    
    # Show progress as this operation can take time
    total_roles = len(built_in_roles)
    for i, role in enumerate(built_in_roles, 1):
        sys.stdout.write(f"\r{Fore.BLUE}Checking role {i}/{total_roles}: {role['displayName']}")
        sys.stdout.flush()
        
        users = get_users_for_role(token, role['id'])
        if users:
            role['users'] = users
            role['user_count'] = len(users)
            roles_with_users.append(role)
    
    print(f"\n\n{Fore.CYAN}{Style.BRIGHT}=== ROLES WITH ASSIGNED USERS ===")
    print(f"Found {len(roles_with_users)} roles with user assignments")
    
    # Sort roles - privileged first, then alphabetically
    roles_with_users.sort(key=lambda r: (not r['is_privileged'], r['displayName'].lower()))
    
    for i, role in enumerate(roles_with_users, 1):
        if role['is_privileged']:
            print(f"{i}. {Fore.RED}{Style.BRIGHT}[PRIVILEGED] {role['displayName']} - {role['user_count']} users{Style.RESET_ALL}")
        else:
            print(f"{i}. {role['displayName']} - {role['user_count']} users")
        
        # Display users for each role
        for user in role.get('users', []):
            user_type_icon = "👤" if user['type'] == 'user' else "👥"
            print(f"   {user_type_icon} {user['displayName']} ({user['id']})")
    
    return roles_with_users

def create_review_for_privileged_roles(reviewer_ids=None):
    """Create access reviews for privileged roles"""
    token = authenticate()
    
    print(f"{Fore.BLUE}Fetching roles from Entra ID...")
    all_roles = get_roles(token)
    built_in_roles = filter_built_in_roles(all_roles)
    
    # Filter privileged roles
    privileged_roles = []
    for role in built_in_roles:
        if role['id'] in PRIVILEGED_ROLES:
            privileged_roles.append(role)
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== PRIVILEGED ROLES SELECTED FOR REVIEW ===")
    print(f"The following {len(privileged_roles)} roles will be reviewed:")
    
    for i, role in enumerate(privileged_roles, 1):
        print(f"{i}. {Fore.RED}{Style.BRIGHT}{role['displayName']}{Style.RESET_ALL} ({role['id']})")
    
    # Confirm with the user
    print(f"\n{Fore.YELLOW}Do you want to create access reviews for these roles? (y/n)")
    if input("> ").lower() != 'y':
        print(f"{Fore.YELLOW}Operation cancelled by user.")
        return
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== CREATING ACCESS REVIEWS ===")
    print(f"Creating reviews for {len(privileged_roles)} privileged roles")
    
    results = []
    success_count = 0
    
    for i, role in enumerate(privileged_roles, 1):
        print(f"Creating review for role {i}/{len(privileged_roles)}: {role['displayName']}... ", end="")
        result = create_access_review(token, role, reviewer_ids)
        results.append(result)
        
        if result['success']:
            print(f"{Fore.GREEN}Success")
            success_count += 1
        else:
            print(f"{Fore.RED}Failed ({result['status_code']})")
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== RESULTS ===")
    print(f"Successfully created {success_count} out of {len(results)} access reviews")
    
    if success_count < len(results):
        print(f"\n{Fore.RED}Errors:")
        for result in results:
            if not result['success']:
                print(f"- {result['role_name']}")
                if 'error' in result:
                    print(f"  Error details: {result['error']}")

def create_review_for_selected_roles(reviewer_id=None):
    """Create access reviews for selected roles"""
    all_roles = list_roles(detailed=False)
    
    while True:
        print(f"\n{Fore.YELLOW}Enter role numbers to create reviews for (comma-separated, e.g. '1,3,5-7'), or 'all' for all roles:")
        selection = input("> ")
        
        if selection.lower() == 'all':
            selected_roles = all_roles
            break
            
        try:
            selected_indices = []
            parts = selection.split(',')
            
            for part in parts:
                part = part.strip()
                if '-' in part:  # Range like 5-7
                    start, end = map(int, part.split('-'))
                    selected_indices.extend(range(start, end + 1))
                else:
                    selected_indices.append(int(part))
            
            # Adjust for 1-based indexing and check bounds
            selected_indices = [i-1 for i in selected_indices if 1 <= i <= len(all_roles)]
            
            if not selected_indices:
                print(f"{Fore.RED}No valid role numbers selected. Please try again.")
                continue
                
            selected_roles = [all_roles[i] for i in selected_indices]
            break
            
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter numbers separated by commas.")
    
    # Show confirmation with selected roles
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SELECTED ROLES FOR REVIEW ===")
    print(f"You've selected {len(selected_roles)} roles for review:")
    
    for i, role in enumerate(selected_roles, 1):
        if role['is_privileged']:
            print(f"{i}. {Fore.RED}{Style.BRIGHT}[PRIVILEGED] {role['displayName']}{Style.RESET_ALL} ({role['id']})")
        else:
            print(f"{i}. {role['displayName']} ({role['id']})")
    
    # Final confirmation
    print(f"\n{Fore.YELLOW}Do you want to create access reviews for these roles? (y/n)")
    if input("> ").lower() != 'y':
        print(f"{Fore.YELLOW}Operation cancelled by user.")
        return
    
    # Now create reviews for selected roles
    token = authenticate()
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== CREATING ACCESS REVIEWS ===")
    print(f"Creating reviews for {len(selected_roles)} selected roles")
    
    results = []
    success_count = 0
    
    for i, role in enumerate(selected_roles, 1):
        print(f"Creating review for role {i}/{len(selected_roles)}: {role['displayName']}... ", end="")
        result = create_access_review(token, role, reviewer_id)
        results.append(result)
        
        if result['success']:
            print(f"{Fore.GREEN}Success")
            success_count += 1
        else:
            print(f"{Fore.RED}Failed ({result['status_code']})")
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== RESULTS ===")
    print(f"Successfully created {success_count} out of {len(results)} access reviews")
    
    if success_count < len(results):
        print(f"\n{Fore.RED}Errors:")
        for result in results:
            if not result['success']:
                print(f"- {result['role_name']}")
                if 'error' in result:
                    error_details = result['error']
                    if isinstance(error_details, dict):
                        error_msg = error_details.get('error', {}).get('message', str(error_details))
                        print(f"  Error details: {error_msg}")
                    else:
                        print(f"  Error details: {error_details}")

def create_review_with_schedule(reviewer_id=None):
    """Create access reviews with customizable schedule frequency"""
    all_roles = list_roles(detailed=False)
    
    # First ask for schedule frequency
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SELECT REVIEW SCHEDULE ===")
    print("How often should the access review occur?")
    print(f"1. Weekly (every week)")
    print(f"2. Monthly (every month)")
    print(f"3. Quarterly (every 3 months)")
    print(f"4. Half-yearly (every 6 months) - Default")
    
    schedule_choice = input(f"\n{Fore.YELLOW}Enter your choice (1-4): ")
    
    frequency = "halfyearly"  # Default
    if schedule_choice == '1':
        frequency = "weekly"
    elif schedule_choice == '2':
        frequency = "monthly"
    elif schedule_choice == '3':
        frequency = "quarterly"
    
    # Now add option to choose between all roles, privileged roles, or selected roles
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SELECT ROLES ===")
    print(f"1. All roles ({len(all_roles)} roles)")
    print(f"2. Privileged roles only")
    print(f"3. Select specific roles")
    
    roles_choice = input(f"\n{Fore.YELLOW}Enter your choice (1-3): ")
    
    selected_roles = []
    
    if roles_choice == '1':
        # All roles
        selected_roles = all_roles
    elif roles_choice == '2':
        # Privileged roles only
        selected_roles = [role for role in all_roles if role.get('is_privileged', False)]
        
        # Display the selected privileged roles
        print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SELECTED PRIVILEGED ROLES ===")
        print(f"Selected {len(selected_roles)} privileged roles:")
        
        for i, role in enumerate(selected_roles, 1):
            print(f"{i}. {Fore.RED}{Style.BRIGHT}{role['displayName']}{Style.RESET_ALL} ({role['id']})")
    else:
        # Let user select specific roles - keep existing code
        while True:
            print(f"\n{Fore.YELLOW}Enter role numbers to create reviews for (comma-separated, e.g. '1,3,5-7'), or 'all' for all roles:")
            selection = input("> ")
            
            if selection.lower() == 'all':
                selected_roles = all_roles
                break
                
            try:
                selected_indices = []
                parts = selection.split(',')
                
                for part in parts:
                    part = part.strip()
                    if '-' in part:  # Range like 5-7
                        start, end = map(int, part.split('-'))
                        selected_indices.extend(range(start, end + 1))
                    else:
                        selected_indices.append(int(part))
                
                # Adjust for 1-based indexing and check bounds
                selected_indices = [i-1 for i in selected_indices if 1 <= i <= len(all_roles)]
                
                if not selected_indices:
                    print(f"{Fore.RED}No valid role numbers selected. Please try again.")
                    continue
                    
                selected_roles = [all_roles[i] for i in selected_indices]
                break
                
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter numbers separated by commas.")
    
    if not selected_roles:
        print(f"{Fore.RED}No roles selected. Operation cancelled.")
        return
    
    # Show confirmation with selected roles
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SELECTED ROLES FOR REVIEW ===")
    print(f"You've selected {len(selected_roles)} roles for review with {frequency} schedule:")
    
    for i, role in enumerate(selected_roles, 1):
        if role.get('is_privileged', False):
            print(f"{i}. {Fore.RED}{Style.BRIGHT}[PRIVILEGED] {role['displayName']}{Style.RESET_ALL} ({role['id']})")
        else:
            print(f"{i}. {role['displayName']} ({role['id']})")
    
    # Final confirmation
    print(f"\n{Fore.YELLOW}Do you want to create scheduled access reviews for these roles? (y/n)")
    if input("> ").lower() != 'y':
        print(f"{Fore.YELLOW}Operation cancelled by user.")
        return
    
    # Now create reviews for selected roles
    token = authenticate()
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== CREATING SCHEDULED ACCESS REVIEWS ===")
    print(f"Creating {frequency} reviews for {len(selected_roles)} selected roles")
    
    from entra_access_review import create_access_review_with_schedule
    
    results = []
    success_count = 0
    
    for i, role in enumerate(selected_roles, 1):
        print(f"Creating {frequency} review for role {i}/{len(selected_roles)}: {role['displayName']}... ", end="")
        result = create_access_review_with_schedule(token, role, reviewer_id, frequency)
        results.append(result)
        
        if result['success']:
            print(f"{Fore.GREEN}Success")
            success_count += 1
        else:
            print(f"{Fore.RED}Failed ({result['status_code']})")
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== RESULTS ===")
    print(f"Successfully created {success_count} out of {len(results)} access reviews")
    
    if success_count < len(results):
        print(f"\n{Fore.RED}Errors:")
        for result in results:
            if not result['success']:
                print(f"- {result['role_name']}")
                if 'error' in result:
                    error_details = result['error']
                    if isinstance(error_details, dict):
                        error_msg = error_details.get('error', {}).get('message', str(error_details))
                        print(f"  Error details: {error_msg}")
                    else:
                        print(f"  Error details: {error_details}")

def manage_existing_reviews():
    """List, view details and delete existing access reviews"""
    token = authenticate()
    
    print(f"{Fore.BLUE}Fetching existing access reviews...")
    reviews = get_reviews_list(token)
    
    if not reviews:
        print(f"{Fore.YELLOW}No access reviews found.")
        return
    
    while True:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}=== EXISTING ACCESS REVIEWS ===")
        print(f"Found {len(reviews)} access reviews:")
        
        # Display available reviews with numbers for selection
        for i, review in enumerate(reviews, 1):
            status = review.get('status', 'Unknown')
            status_color = Fore.GREEN if status == 'Active' else Fore.YELLOW
            print(f"{i}. {review['displayName']} - {status_color}{status}{Style.RESET_ALL}")
        
        print(f"\n{Fore.YELLOW}Options:")
        print("1. View review details")
        print("2. Delete a review")
        print("0. Back to main menu")
        
        choice = input(f"\n{Fore.YELLOW}Enter your choice (0-2): ")
        
        if choice == '1':
            view_review_details(token, reviews)
            # Add pause after viewing details to ensure user sees the information
            input(f"\n{Fore.YELLOW}Press Enter to return to the reviews list...")
        elif choice == '2':
            delete_review(token, reviews)
            # Add pause after deletion to ensure user sees results
            input(f"\n{Fore.YELLOW}Press Enter to continue to the updated reviews list...")
        elif choice == '0':
            break
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.")

def get_reviews_list(token):
    """Get list of existing access reviews"""
    from entra_access_review import list_access_reviews
    
    reviews = list_access_reviews(token)
    return reviews

def view_review_details(token, reviews):
    """View details of one or multiple access review(s)"""
    from entra_access_review import get_access_review_status
    
    try:
        print(f"\n{Fore.YELLOW}Enter the number(s) of the review(s) to view details (comma-separated, e.g. '1,3,5-7'), or 'all' for all reviews:")
        selection = input("> ")
        
        # Handle different selection formats
        selected_indices = []
        
        if selection.lower() == 'all':
            # All reviews
            selected_indices = list(range(len(reviews)))
        else:
            try:
                parts = selection.split(',')
                
                for part in parts:
                    part = part.strip()
                    if '-' in part:  # Range like 5-7
                        start, end = map(int, part.split('-'))
                        selected_indices.extend(range(start-1, end))  # Adjust for 0-based indexing
                    else:
                        selected_indices.append(int(part) - 1)  # Adjust for 0-based indexing
                
                # Check for valid indices
                selected_indices = [i for i in selected_indices if 0 <= i < len(reviews)]
                
                if not selected_indices:
                    print(f"{Fore.RED}No valid review numbers selected.")
                    return
                    
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter numbers separated by commas.")
                return
        
        # Get selected reviews
        selected_reviews = [reviews[i] for i in selected_indices]
        
        # Display details for each selected review
        for review_index, review in enumerate(selected_reviews):
            if review_index > 0:
                # Add a separator between reviews and pause for better readability
                print(f"\n{Fore.YELLOW}Press Enter to view the next review...")
                input()
                
            review_id = review['id']
            
            print(f"{Fore.BLUE}Fetching details for review ({review_index + 1}/{len(selected_reviews)}): {review['displayName']}...")
            details = get_access_review_status(token, review_id)
            
            if not details.get('success', True):
                print(f"{Fore.RED}Error fetching review details: {details.get('error', 'Unknown error')}")
                continue
            
            # Clear some space to make details more visible
            print("\n\n")
            print(f"{Fore.CYAN}{Style.BRIGHT}{'='*50}")    
            print(f"{Fore.CYAN}{Style.BRIGHT}=== ACCESS REVIEW DETAILS ({review_index + 1}/{len(selected_reviews)}) ===")
            print(f"{Fore.CYAN}{Style.BRIGHT}{'='*50}")
            print(f"Name: {details['displayName']}")
            print(f"ID: {details.get('id', 'Unknown')}")
            print(f"Status: {details.get('status', 'Unknown')}")
            print(f"Created: {details.get('createdDateTime', 'Unknown')}")
            
            # Show scope details
            if 'scope' in details and 'resourceScopes' in details['scope']:
                print(f"\n{Fore.CYAN}Resource Scope:")
                for resource in details['scope'].get('resourceScopes', []):
                    query = resource.get('query', 'Unknown')
                    if 'roleDefinitions/' in query:
                        role_id = query.split('roleDefinitions/')[1]
                        print(f"• Role: {role_id}")
                    else:
                        print(f"• {query}")
            
            # Show schedule settings if available
            if 'settings' in details and 'recurrence' in details['settings']:
                recurrence = details['settings']['recurrence']
                print(f"\n{Fore.CYAN}Review Schedule:")
                
                pattern = recurrence.get('pattern', {})
                pattern_type = pattern.get('type', 'Unknown')
                interval = pattern.get('interval', 'Unknown')
                
                if pattern_type == 'weekly':
                    print(f"Frequency: Weekly (every {interval} week(s))")
                elif pattern_type == 'monthly':
                    if interval == 1:
                        print(f"Frequency: Monthly")
                    elif interval == 3:
                        print(f"Frequency: Quarterly")
                    elif interval == 6:
                        print(f"Frequency: Semi-annual")
                    elif interval == 12:
                        print(f"Frequency: Annual")
                    else:
                        print(f"Frequency: Every {interval} months")
                else:
                    print(f"Frequency: {pattern_type} (interval: {interval})")
                    
                # Show additional settings
                auto_apply = details['settings'].get('autoApplyDecisionsEnabled', False)
                justification = details['settings'].get('justificationRequiredOnApproval', False)
                recommendations = details['settings'].get('recommendationsEnabled', False)
                
                print(f"\n{Fore.CYAN}Review Settings:")
                print(f"Duration: {details['settings'].get('instanceDurationInDays', 'Unknown')} days")
                print(f"Auto-apply decisions: {'Yes' if auto_apply else 'No'}")
                print(f"Justification required: {'Yes' if justification else 'No'}")
                print(f"Recommendations enabled: {'Yes' if recommendations else 'No'}")
            
            # Show instances (actual review cycles)
            if 'instances' in details and details['instances']:
                print(f"\n{Fore.CYAN}Review Instances (Cycles):")
                for i, instance in enumerate(details['instances'], 1):
                    status = instance.get('status', 'Unknown')
                    start_date = instance.get('startDateTime', 'Unknown')
                    end_date = instance.get('endDateTime', 'Unknown')
                    
                    status_color = Fore.GREEN
                    if status == 'InProgress':
                        status_color = Fore.CYAN
                    elif status == 'NotStarted':
                        status_color = Fore.YELLOW
                    elif status == 'Failed':
                        status_color = Fore.RED
                    
                    print(f"{i}. {start_date} to {end_date} - Status: {status_color}{status}{Style.RESET_ALL}")
            
            # Show reviewers
            if 'reviewers' in details:
                print(f"\n{Fore.CYAN}Reviewers:")
                for reviewer in details.get('reviewers', []):
                    query = reviewer.get('query', 'Unknown')
                    if '/users/' in query:
                        user_id = query.split('/users/')[1]
                        print(f"• User: {user_id}")
                    else:
                        print(f"• {query}")
            
            print(f"{Fore.CYAN}{Style.BRIGHT}{'='*50}")
    
    except ValueError:
        print(f"{Fore.RED}Invalid input. Please enter a number.")
    except Exception as e:
        print(f"{Fore.RED}Error: {str(e)}")
        # We don't immediately return to the list - we'll pause at the caller

def delete_review(token, reviews):
    """Delete one or multiple access reviews"""
    from entra_access_review import delete_access_review
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== DELETE ACCESS REVIEWS ===")
    print(f"Available reviews:")
    
    # Display available reviews with numbers for selection
    for i, review in enumerate(reviews, 1):
        status = review.get('status', 'Active')
        status_color = Fore.GREEN if status == 'Active' else Fore.YELLOW
        print(f"{i}. {review['displayName']} - {status_color}{status}{Style.RESET_ALL}")
    
    print(f"\n{Fore.YELLOW}Enter the number(s) of the review(s) to delete (comma-separated, e.g. '1,3,5-7'), or 'all' for all reviews:")
    
    selection = input("> ")
    
    # Handle different selection formats
    selected_indices = []
    
    if selection.lower() == 'all':
        # All reviews
        selected_indices = list(range(len(reviews)))
    else:
        try:
            parts = selection.split(',')
            
            for part in parts:
                part = part.strip()
                if '-' in part:  # Range like 5-7
                    start, end = map(int, part.split('-'))
                    selected_indices.extend(range(start-1, end))  # Adjust for 0-based indexing
                else:
                    selected_indices.append(int(part) - 1)  # Adjust for 0-based indexing
            
            # Check for valid indices
            selected_indices = [i for i in selected_indices if 0 <= i < len(reviews)]
            
            if not selected_indices:
                print(f"{Fore.RED}No valid review numbers selected.")
                return
                
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter numbers separated by commas.")
            return
    
    # Confirm deletion
    selected_reviews = [reviews[i] for i in selected_indices]
    
    print(f"\n{Fore.RED}Warning! You are about to delete the following {len(selected_reviews)} access review(s):")
    for i, review in enumerate(selected_reviews, 1):
        print(f"{i}. {review['displayName']} (ID: {review['id']})")
    
    print(f"\n{Fore.YELLOW}Are you sure you want to delete these reviews? This action cannot be undone. (y/n)")
    
    if input("> ").lower() != 'y':
        print(f"{Fore.YELLOW}Operation cancelled by user.")
        return
    
    # Process deletions
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== DELETING ACCESS REVIEWS ===")
    success_count = 0
    failed = []
    
    for i, review in enumerate(selected_reviews, 1):
        print(f"Deleting review {i}/{len(selected_reviews)}: {review['displayName']}... ", end="")
        result = delete_access_review(token, review['id'])
        
        if result['success']:
            print(f"{Fore.GREEN}Success")
            success_count += 1
        else:
            print(f"{Fore.RED}Failed ({result.get('status_code', 'Unknown error')})")
            failed.append((review['displayName'], result.get('error', 'Unknown error')))
    
    # Show summary
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== RESULTS ===")
    print(f"Successfully deleted {success_count} out of {len(selected_reviews)} access reviews")
    
    if failed:
        print(f"\n{Fore.RED}Errors:")
        for name, error in failed:
            print(f"- {name}")
            if isinstance(error, dict):
                error_msg = error.get('error', {}).get('message', str(error))
                print(f"  Error details: {error_msg}")
            else:
                print(f"  Error details: {error}")
    
    # Remove deleted reviews from the list
    if success_count > 0:
        # We need to remove in reverse order to avoid index shifting
        for i in sorted(selected_indices, reverse=True):
            if i < len(reviews):  # Safety check
                reviews.pop(i)
    
    # Don't immediately return to the reviews list - we'll pause at the caller

def verify_entra_user(token, user_id):
    """Verify if a user exists in Entra ID
    
    Args:
        token: Authentication token
        user_id: User's object ID to verify
        
    Returns:
        Tuple of (exists, display_name, user_principal_name) where:
        - exists: Boolean indicating if user exists
        - display_name: User's display name (or None if not found)
        - user_principal_name: User's UPN (or None if not found)
    """
    headers = {"Authorization": f"Bearer {token}"}
    user_url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    
    try:
        response = requests.get(user_url, headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            return (
                True, 
                user_data.get('displayName', 'Unknown'), 
                user_data.get('userPrincipalName', 'Unknown')
            )
        else:
            return (False, None, None)
    except Exception as e:
        print(f"{Fore.RED}Error verifying user: {str(e)}")
        return (False, None, None)

def verify_reviewer_ids(token, reviewer_ids):
    """Verify if multiple reviewer IDs exist in Entra ID
    
    Args:
        token: Authentication token
        reviewer_ids: List of reviewer IDs to verify
        
    Returns:
        Dictionary with validation results for each ID
    """
    print(f"{Fore.BLUE}Verifying reviewer IDs in Entra ID...")
    
    results = {}
    valid_count = 0
    invalid_count = 0
    
    # Show progress when checking multiple reviewers
    total = len(reviewer_ids)
    
    for i, reviewer_id in enumerate(reviewer_ids, 1):
        sys.stdout.write(f"\r{Fore.BLUE}Checking reviewer {i}/{total}: {reviewer_id}")
        sys.stdout.flush()
        
        exists, name, upn = verify_entra_user(token, reviewer_id)
        
        results[reviewer_id] = {
            "exists": exists,
            "display_name": name,
            "upn": upn
        }
        
        if exists:
            valid_count += 1
        else:
            invalid_count += 1
    
    # Clear the progress line
    print()
    
    print(f"{Fore.GREEN}Verification complete: {valid_count} valid, {invalid_count} invalid")
    
    return results

def collect_reviewer_ids():
    """Collect and validate reviewer IDs
    
    Returns:
        List of validated reviewer IDs
    """
    reviewer_ids = []
    
    print(f"\n{Fore.YELLOW}Enter Object IDs of users who should review access (one per line, or multiple IDs separated by commas):")
    print(f"{Fore.BLUE}(These should be valid Entra ID user object IDs)")
    print(f"{Fore.BLUE}(Enter a blank line when done)")
    
    while True:
        reviewer_input = input("> ").strip()
        if not reviewer_input:
            break
            
        # Split by comma if multiple IDs are provided on one line
        if "," in reviewer_input:
            id_list = [id.strip() for id in reviewer_input.split(",")]
        else:
            id_list = [reviewer_input]
        
        for reviewer_id in id_list:
            # Validate ID format
            if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', reviewer_id, re.I):
                print(f"{Fore.YELLOW}Warning: The ID {reviewer_id} doesn't appear to be in the correct format.")
                print(f"It should be a GUID like: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
                print(f"Do you want to use this ID anyway? (y/n)")
                if input("> ").lower() != 'y':
                    continue
                    
            reviewer_ids.append(reviewer_id)
    
    if not reviewer_ids:
        print(f"{Fore.RED}No reviewer IDs entered.")
        return None
    
    # Option to verify reviewer IDs
    print(f"\n{Fore.YELLOW}Do you want to verify these reviewer IDs exist in Entra ID? (y/n)")
    if input("> ").lower() == 'y':
        token = authenticate()
        verification_results = verify_reviewer_ids(token, reviewer_ids)
        
        # Display results
        print(f"\n{Fore.CYAN}{Style.BRIGHT}=== REVIEWER VERIFICATION RESULTS ===")
        
        all_valid = True
        invalid_ids = []
        
        for reviewer_id, result in verification_results.items():
            if result['exists']:
                print(f"{Fore.GREEN}✓ {reviewer_id} - {result['display_name']} ({result['upn']})")
            else:
                print(f"{Fore.RED}✗ {reviewer_id} - User not found in Entra ID")
                all_valid = False
                invalid_ids.append(reviewer_id)
        
        if not all_valid:
            print(f"\n{Fore.YELLOW}Some reviewer IDs were not found in Entra ID.")
            print("Options:")
            print("1. Remove invalid reviewers")
            print("2. Keep all reviewers (not recommended)")
            print("3. Start over")
            
            choice = input(f"\n{Fore.YELLOW}Enter your choice (1-3): ")
            
            if choice == '1':
                # Remove invalid reviewers
                reviewer_ids = [id for id in reviewer_ids if id not in invalid_ids]
                print(f"{Fore.GREEN}Removed {len(invalid_ids)} invalid reviewer(s).")
            elif choice == '3':
                # Start over
                print(f"{Fore.YELLOW}Starting over...")
                return collect_reviewer_ids()
            # For choice 2, we keep all IDs as is
    
    print(f"{Fore.GREEN}Added {len(reviewer_ids)} reviewers.")
    return reviewer_ids

def set_custom_reviewer(current_reviewer_id=None):
    """Set a custom reviewer for access reviews
    
    Args:
        current_reviewer_id: Current reviewer ID (if any)
        
    Returns:
        The new reviewer ID or None if canceled
    """
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SET CUSTOM REVIEWER ===")
    
    if current_reviewer_id:
        print(f"Current reviewer ID: {Fore.GREEN}{current_reviewer_id}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Options:")
        print("1. Change reviewer")
        print("2. Clear reviewer (use no reviewer)")
        print("0. Cancel")
        
        choice = input(f"\n{Fore.YELLOW}Enter your choice (0-2): ")
        
        if choice == '0':
            return current_reviewer_id
        elif choice == '2':
            print(f"{Fore.GREEN}Reviewer cleared. Access reviews will be created without a specific reviewer.")
            return None
    else:
        print(f"No reviewer currently configured. Access reviews are created without a specific reviewer.")
        choice = "1"
    
    if choice == '1':
        print(f"\n{Fore.YELLOW}Enter the Object ID of the user who should review access:")
        print(f"{Fore.BLUE}(This should be a valid Entra ID user object ID)")
        reviewer_id = input("> ").strip()
        
        if not reviewer_id:
            print(f"{Fore.RED}No reviewer ID entered. Operation cancelled.")
            return current_reviewer_id
        
        # Validate the ID format - basic check for GUID format
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', reviewer_id, re.I):
            print(f"{Fore.YELLOW}Warning: The ID entered doesn't appear to be in the correct format.")
            print(f"It should be a GUID like: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
            print(f"Do you want to use this ID anyway? (y/n)")
            if input("> ").lower() != 'y':
                return current_reviewer_id
        
        # Option to verify the reviewer ID exists in Entra ID
        print(f"\n{Fore.YELLOW}Do you want to verify this user ID exists in Entra ID? (y/n)")
        if input("> ").lower() == 'y':
            token = authenticate()
            exists, name, upn = verify_entra_user(token, reviewer_id)
            
            if exists:
                print(f"{Fore.GREEN}User found: {name} ({upn})")
                print(f"{Fore.YELLOW}Do you want to use this user as reviewer? (y/n)")
                if input("> ").lower() != 'y':
                    return current_reviewer_id
            else:
                print(f"{Fore.RED}Error: User not found in Entra ID.")
                print(f"{Fore.YELLOW}Do you still want to use this ID? (y/n)")
                if input("> ").lower() != 'y':
                    return current_reviewer_id
        
        print(f"{Fore.GREEN}Reviewer set successfully. Access reviews will be assigned to this reviewer.")
        return reviewer_id
    
    return current_reviewer_id

def set_custom_reviewers(current_reviewer_ids=None):
    """Set custom reviewers for access reviews
    
    Args:
        current_reviewer_ids: Current reviewer IDs (if any)
        
    Returns:
        List of reviewer IDs or None if canceled
    """
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== SET CUSTOM REVIEWERS ===")
    
    if current_reviewer_ids:
        if isinstance(current_reviewer_ids, str):
            current_reviewer_ids = [current_reviewer_ids]
            
        print(f"Current reviewers:")
        for i, rid in enumerate(current_reviewer_ids, 1):
            print(f"{i}. {Fore.GREEN}{rid}{Style.RESET_ALL}")
            
        print(f"\n{Fore.YELLOW}Options:")
        print("1. Add more reviewers")
        print("2. Replace all reviewers")
        print("3. Clear reviewers (use no reviewer)")
        print("0. Cancel")
        
        choice = input(f"\n{Fore.YELLOW}Enter your choice (0-3): ")
        
        if choice == '0':
            return current_reviewer_ids
        elif choice == '3':
            print(f"{Fore.GREEN}Reviewers cleared. Access reviews will be created without specific reviewers.")
            return None
        elif choice == '1':
            # Dodajemy do istniejącej listy
            new_ids = collect_reviewer_ids()
            if new_ids:
                return current_reviewer_ids + new_ids
            return current_reviewer_ids
    else:
        print(f"No reviewers currently configured. Access reviews are created without specific reviewers.")
        choice = "2"
    
    if choice == '2':
        return collect_reviewer_ids()
    
    return current_reviewer_ids

def main():
    """Main function with simple menu"""
    try:
        display_welcome_banner()
        
        # Variable to store custom reviewer IDs - initially None
        custom_reviewer_id = None
        
        while True:
            reviewer_status = "Not configured"
            if custom_reviewer_id:
                if isinstance(custom_reviewer_id, list):
                    reviewer_status = f"Configured ({len(custom_reviewer_id)} reviewers)"
                else:
                    reviewer_status = "Configured (1 reviewer)"
                    
            print(f"\n{Fore.CYAN}{Style.BRIGHT}=== MICROSOFT ENTRA ID ACCESS REVIEW TOOL ===")
            print("1. List all roles")
            print("2. List roles with assigned users")
            print("3. Create access reviews for privileged roles")
            print("4. Create access reviews for selected roles")
            print("5. Create access reviews with custom schedule")
            print("6. View or delete existing access reviews")
            print(f"7. {Fore.YELLOW}Set custom reviewer(s){Fore.CYAN} [{Fore.GREEN if custom_reviewer_id else Fore.RED}{reviewer_status}{Fore.CYAN}]")
            print("0. Exit")
            
            choice = input(f"\n{Fore.YELLOW}Enter your choice (0-7): ")
            
            if choice == '1':
                list_roles()
            elif choice == '2':
                list_roles_with_users()
            elif choice == '3':
                create_review_for_privileged_roles(custom_reviewer_id)
            elif choice == '4':
                create_review_for_selected_roles(custom_reviewer_id)
            elif choice == '5':
                create_review_with_schedule(custom_reviewer_id)
            elif choice == '6':
                manage_existing_reviews()
            elif choice == '7':
                custom_reviewer_id = set_custom_reviewers(custom_reviewer_id)
            elif choice == '0':
                # Replace simple "Goodbye" with a more informative exit message
                farewell_message = f"""
{Fore.CYAN}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          THANK YOU FOR USING THE ACCESS REVIEW TOOL       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.GREEN}Your Entra ID security reviews have been managed successfully.
Remember to monitor the progress of your access reviews in the 
Microsoft Entra admin center: https://entra.microsoft.com

{Fore.BLUE}For more tools and projects, visit: {Fore.CYAN}https://github.com/p4pryk{Style.RESET_ALL}
"""
                print(farewell_message)
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.")
            
            # After any action, prompt to continue
            input(f"\n{Fore.YELLOW}Press Enter to continue...")
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user. Exiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()
