# Migration Guide: Unified Persistent UI System

This guide helps you migrate from the existing persistent button systems to the new unified system.

## Overview

The unified system consolidates three previous approaches:
- `persistent_buttons.py` (database-backed)
- `persistent_button_system.py` (DynamicItem-based)
- `persistent_views.py` (concrete implementations)

## Key Benefits

1. **Single API**: One consistent interface for all persistent UI
2. **Performance**: State encoding for speed, database fallback for complexity
3. **Maintainability**: Centralized system reduces duplication
4. **OOP Design**: Proper inheritance and separation of concerns

## Migration Steps

### 1. Update Imports

**Before:**
```python
from utils.persistent_buttons import PersistentView, PersistentButtonHandler
from utils.persistent_views import create_persistent_stats_view
```

**After:**
```python
from utils.unified_persistent_ui import PersistentView, ButtonHandler
from utils.unified_persistent_ui import create_navigation_view, create_welcome_view
```

### 2. Update Handler Classes

**Before (persistent_buttons.py style):**
```python
class MyButtonHandler(PersistentButtonHandler):
    def get_button_config(self) -> Dict[str, Any]:
        return {'style': discord.ButtonStyle.primary, 'label': 'Click Me'}
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        # Handle interaction
        pass
```

**After (unified system):**
```python
class MyButtonHandler(ButtonHandler):
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        return {'style': discord.ButtonStyle.primary, 'label': 'Click Me'}
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        # Handle interaction - same logic
        pass
```

### 3. Update View Creation

**Before:**
```python
# Old way with persistent_views.py
view = await create_persistent_stats_view(context, user_id, guild_id, total_pages)
```

**After:**
```python
# New unified way
view = create_navigation_view(context, user_id, current_page, total_pages, guild_id)
```

### 4. Update Manual Button Addition

**Before:**
```python
view = PersistentView(context, "my_view", guild_id=guild_id)
await view.add_persistent_button(
    handler=my_handler,
    custom_id=f"my_button_{user_id}",
    button_type=ButtonType.ACTION,
    data={'key': 'value'},
    user_id=user_id,
    expires_in=timedelta(minutes=30)
)
```

**After:**
```python
view = PersistentView(context)
custom_id = view.add_button(
    handler_name='MyButtonHandler',
    user_id=user_id,
    action=ButtonAction.ACTION,
    data={'key': 'value'},
    guild_id=guild_id,
    expires_in=timedelta(minutes=30)
)
```

### 5. Update Context Initialization

**Before:**
```python
# In context.py
from utils.persistent_button_system import initialize_button_system
self.button_manager = await initialize_button_system(self)
```

**After:**
```python
# Already updated in context.py
from utils.unified_persistent_ui import initialize_unified_ui_system
self.ui_manager = await initialize_unified_ui_system(self)
```

## Modal Migration

### Before (custom_quiz.py style):
```python
class QuizCreationModal(discord.ui.Modal, title='Create Custom Quiz'):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    quiz_name = discord.ui.TextInput(
        label='Quiz Name',
        placeholder='Enter a name for your quiz',
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction):
        # Manual validation and handling
        pass
```

### After (standardized modals):
```python
from utils.standardized_modals import create_quiz_modal

# In your cog
async def show_quiz_creation(self, interaction: discord.Interaction):
    async def handle_quiz_creation(interaction: discord.Interaction, values: Dict[str, str]):
        # Handle the submitted quiz data
        quiz_name = values['name']
        topic = values['topic']
        # ... rest of handling
    
    modal = create_quiz_modal(self.context, handle_quiz_creation)
    await interaction.response.send_modal(modal)
```

## Component-by-Component Migration

### Stats Views

**Before:**
```python
# From cogs/stats.py
class StatsPaginatedView(discord.ui.View):
    def __init__(self, embeds, author_id, timeout=180):
        # Manual pagination implementation
        pass
```

**After:**
```python
# Use unified system
from utils.unified_persistent_ui import create_navigation_view

# In your stats command
view = create_navigation_view(
    context=self.context,
    user_id=interaction.user.id,
    current_page=0,
    total_pages=len(embeds),
    guild_id=interaction.guild.id if interaction.guild else None
)
await interaction.response.send_message(embed=embeds[0], view=view)
```

### FAQ Views

**Before:**
```python
# From cogs/faq.py
class FAQView(discord.ui.View):
    # Complex navigation with first/prev/next/last buttons
    pass
```

**After:**
```python
# Use existing FAQNavigationHandler through unified system
view = PersistentView(context)
view.add_button(
    'FAQNavigationHandler',
    interaction.user.id,
    ButtonAction.NAVIGATE,
    {'direction': 'next', 'page': current_page, 'total': total_pages, 'faq_data': faq_data},
    guild_id,
    timedelta(minutes=15)
)
```

### Welcome Views

**Before:**
```python
# Manual button creation
class WelcomeView(discord.ui.View):
    @discord.ui.button(label="Start Quiz", style=discord.ButtonStyle.success)
    async def start_quiz(self, interaction, button):
        # Handle quiz start
        pass
```

**After:**
```python
# Use factory function
from utils.unified_persistent_ui import create_welcome_view

view = create_welcome_view(context, guild_id)
await interaction.response.send_message(embed=welcome_embed, view=view)
```

## Handler Registration

### Automatic Registration

**Before:**
```python
# Manual registration in multiple places
manager.register_handler(MyHandler)
```

**After:**
```python
# Automatic registration from specialized_handlers module
from utils import specialized_handlers
manager.register_handlers_from_module(specialized_handlers)
```

### Custom Handler Registration

```python
# In your cog setup
async def setup(bot):
    # Register custom handlers
    context = bot.context
    if hasattr(context, 'ui_manager'):
        context.ui_manager.register_handler('MyCustomHandler', MyCustomHandler)
```

## Testing Your Migration

### 1. Verify Handler Registration
```python
# Check if handlers are registered
print(f"Registered handlers: {context.ui_manager.handlers.keys()}")
```

### 2. Test Button Functionality
```python
# Create a test view and verify buttons work
view = PersistentView(context)
custom_id = view.add_button(
    'TestHandler', user_id, ButtonAction.ACTION, {'test': True}
)
print(f"Created button with ID: {custom_id}")
```

### 3. Check Database Persistence
```python
# Verify database fallback works for complex state
try:
    view.add_button(
        'ComplexHandler', user_id, ButtonAction.ACTION,
        {'very_large_data': 'x' * 1000},  # Should trigger database fallback
        persistence_mode=PersistenceMode.DATABASE
    )
    print("Database persistence working")
except Exception as e:
    print(f"Database persistence issue: {e}")
```

## Common Issues and Solutions

### 1. Missing Handler Registration

**Issue:** `Button handler not available` error

**Solution:**
```python
# Ensure handlers are registered in context initialization
context.ui_manager.register_handler('YourHandler', YourHandlerClass)
```

### 2. State Too Complex Error

**Issue:** `State too complex for encoding` error

**Solution:**
```python
# Use database persistence for complex state
view.add_button(
    handler_name, user_id, action, data,
    persistence_mode=PersistenceMode.DATABASE
)
```

### 3. Migration Compatibility

**Issue:** Old code still using deprecated systems

**Solution:**
```python
# Create compatibility layer if needed
from utils.unified_persistent_ui import PersistentView as NewPersistentView

# Temporary compatibility alias
PersistentView = NewPersistentView
```

## Performance Considerations

### State Encoding vs Database

- **Use State Encoding** for simple data (< 80 characters when encoded)
- **Use Database** for complex data, large objects, or long-term persistence
- **Use Memory** for temporary buttons that don't need persistence

### Button Lifecycle

- Set appropriate expiration times
- Clean up unused database entries
- Use public buttons (user_id=0) for global actions

## Rollback Plan

If issues arise, you can temporarily revert:

1. **Comment out unified system initialization**:
```python
# In context.py
# self.ui_manager = await initialize_unified_ui_system(self)
# Temporarily use old system
from utils.persistent_button_system import initialize_button_system
self.button_manager = await initialize_button_system(self)
```

2. **Revert imports in affected files**
3. **Test that old system still works**
4. **Fix issues in unified system**
5. **Re-enable unified system**

## Next Steps

After migration:

1. **Remove deprecated files** (when confident):
   - `utils/persistent_buttons.py`
   - `utils/persistent_button_system.py` 
   - `utils/persistent_views.py`

2. **Update documentation** to reference unified system

3. **Create new components** using unified patterns

4. **Monitor performance** and adjust persistence modes as needed

## Support

If you encounter issues during migration:

1. Check the unified system logs for error details
2. Verify handler registration in the context
3. Test with simple button configurations first
4. Gradually migrate complex components

The unified system is designed to be backward compatible and should handle most existing use cases with minimal changes.