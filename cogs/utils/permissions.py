"""Permission utilities for cogs."""

import discord
from discord import Member, User, Guild
from discord.ext import commands
from typing import Union, Optional, List
import logging

logger = logging.getLogger("bot.cogs.utils.permissions")


def is_bot_admin(user_id: int, admin_user_ids: List[int]) -> bool:
    """
    Check if a user is a bot admin.
    
    Args:
        user_id: The user ID to check
        admin_user_ids: List of admin user IDs
        
    Returns:
        bool: True if user is a bot admin
    """
    return user_id in admin_user_ids


def has_server_permission(member: Member, permission: str) -> bool:
    """
    Check if a member has a specific permission in the server.
    
    Args:
        member: The Discord member to check
        permission: The permission name (e.g., 'manage_guild', 'administrator')
        
    Returns:
        bool: True if member has the permission
    """
    if not isinstance(member, Member):
        return False
    
    # Get the permission attribute
    perm_attr = getattr(member.guild_permissions, permission, None)
    if perm_attr is None:
        logger.warning(f"Unknown permission: {permission}")
        return False
    
    return perm_attr is True


def has_role(member: Member, role_names: List[str]) -> bool:
    """
    Check if a member has any of the specified roles.
    
    Args:
        member: The Discord member to check
        role_names: List of role names to check for
        
    Returns:
        bool: True if member has any of the roles
    """
    if not isinstance(member, Member):
        return False
    
    member_role_names = [role.name.lower() for role in member.roles]
    
    for role_name in role_names:
        if role_name.lower() in member_role_names:
            return True
    
    return False


def check_admin_permissions(
    user: Union[Member, User],
    admin_users: List[int],
    admin_roles: List[str]
) -> bool:
    """
    Check if a user has admin permissions.
    
    Args:
        user: The user to check
        admin_users: List of admin user IDs
        admin_roles: List of admin role names
        
    Returns:
        bool: True if user has admin permissions
    """
    # Check if user is a bot admin
    if is_bot_admin(user.id, admin_users):
        return True
    
    # Check if user is the bot owner
    if hasattr(user, 'guild') and user.guild:
        if user.id == user.guild.owner_id:
            return True
    
    # Check server permissions if member
    if isinstance(user, Member):
        # Check if they have administrator permission
        if has_server_permission(user, 'administrator'):
            return True
        
        # Check if they have any admin roles
        if has_role(user, admin_roles):
            return True
    
    return False


def check_manage_permissions(member: Member) -> bool:
    """
    Check if a member has management permissions.
    
    Args:
        member: The Discord member to check
        
    Returns:
        bool: True if member has management permissions
    """
    if not isinstance(member, Member):
        return False
    
    # Check for various management permissions
    management_perms = [
        'manage_guild',
        'manage_channels',
        'manage_roles',
        'administrator'
    ]
    
    for perm in management_perms:
        if has_server_permission(member, perm):
            return True
    
    return False


def check_bot_permissions(ctx: commands.Context, *permissions: str) -> bool:
    """
    Check if the bot has required permissions in the context.
    
    Args:
        ctx: The command context
        *permissions: Permission names to check
        
    Returns:
        bool: True if bot has all required permissions
    """
    if not ctx.guild:
        # DM context, bot has all permissions
        return True
    
    bot_member = ctx.guild.me
    
    for permission in permissions:
        if not has_server_permission(bot_member, permission):
            return False
    
    return True


class PermissionChecks:
    """Predefined permission checks for common use cases."""
    
    @staticmethod
    def is_admin(admin_users: List[int], admin_roles: List[str]):
        """Create a check for admin permissions."""
        async def predicate(ctx: commands.Context) -> bool:
            return check_admin_permissions(ctx.author, admin_users, admin_roles)
        return commands.check(predicate)
    
    @staticmethod
    def is_manager():
        """Create a check for management permissions."""
        async def predicate(ctx: commands.Context) -> bool:
            if not ctx.guild:
                return False
            return check_manage_permissions(ctx.author)
        return commands.check(predicate)
    
    @staticmethod
    def bot_has_permissions(*permissions: str):
        """Create a check for bot permissions."""
        async def predicate(ctx: commands.Context) -> bool:
            return check_bot_permissions(ctx, *permissions)
        return commands.check(predicate)
    
    @staticmethod
    def in_guild():
        """Create a check that command is used in a guild."""
        async def predicate(ctx: commands.Context) -> bool:
            return ctx.guild is not None
        return commands.check(predicate)