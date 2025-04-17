def get_admin_menu(active_menu=None, active_submenu=None):
    """
    Get the admin menu structure with active state for the current view
    
    Args:
        active_menu: Current active main menu item
        active_submenu: Current active submenu item
    
    Returns:
        Dictionary with menu structure
    """
    menu = {
        'administration': {
            'name': 'Administration',
            'icon': 'users',
            'active': active_menu == 'administration',
            'items': [
                {
                    'name': 'User Management',
                    'url': 'account:user_list',
                    'active': active_submenu == 'user_management',
                    'icon': 'user-check',
                    'items': [
                        {
                            'name': 'All Users',
                            'url': 'account:user_list',
                            'active': False, 
                        },
                        {
                            'name': 'Teachers',
                            'url': 'account:user_list', 
                            'params': {'type': 'teacher'},
                            'active': False,
                        },
                        {
                            'name': 'Students',
                            'url': 'account:user_list',
                            'params': {'type': 'student'},
                            'active': False,
                        },
                    ]
                },
                {
                    'name': 'User Settings',
                    'active': active_submenu == 'user_settings',
                    'icon': 'settings',
                    'items': [
                        {
                            'name': 'Account',
                            'url': '#',
                            'active': False,
                        },
                        {
                            'name': 'Security',
                            'url': '#',
                            'active': False,
                        },
                        {
                            'name': 'Preferences',
                            'url': '#',
                            'active': False,
                        },
                    ]
                },
                {
                    'name': 'Roles & Permissions',
                    'url': 'account:role_list',
                    'active': active_submenu == 'roles_permissions',
                    'icon': 'shield-check',
                    'items': [
                        {
                            'name': 'Roles',
                            'url': 'account:role_list',
                            'active': False,
                        },
                        {
                            'name': 'Permissions',
                            'url': 'account:permission_list',
                            'active': False,
                        },
                    ]
                },
            ]
        }
    }
    
    return menu