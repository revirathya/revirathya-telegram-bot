import os
import pytz
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.components import calendar, numpad
from src.helpers.bot import BotReplyMarkupHelper
from src.modules.bootstrap import Usecase


# Conversation
class FinanceConversation:
    __reply_h: BotReplyMarkupHelper
    __tz: pytz.timezone
    __usecase: Usecase

    __calendar_c: calendar.CalenderComponent
    __numpad_c: numpad.NumpadComponent
    __template_dir: str

    # Constant
    STATES = {
        state: i
        for i, state in enumerate([
            "INPUT_ACTION",
            "INPUT_DATE",
            "INPUT_BUDGET_GROUP",
            "INPUT_BUDGET_TYPE",
            "INPUT_DESCRIPTION",
            "INPUT_AMOUNT",
            "INPUT_CONFIRMATION",
            "CALENDAR_CONTROL",
            "CALENDAR_END_CONTROL",
            "NUMPAD_CONTROL",
            "NUMPAD_END_CONTROL",
        ])
    }

    def __init__(self, reply_h: BotReplyMarkupHelper, tz: pytz.timezone, usecase: Usecase):
        self.__reply_h = reply_h
        self.__tz = tz
        self.__usecase = usecase

        self.__calendar_c = calendar.CalenderComponent()
        self.__numpad_c = numpad.NumpadComponent()
        self.__template_dir = os.path.join(os.path.dirname(__file__), "templates")
    

    def get_conversation(self) -> ConversationHandler:
        # Define Flow
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("finance", self.__start),
            ],
            states={
                FinanceConversation.STATES["INPUT_ACTION"]: [
                    CallbackQueryHandler(self.__input_date)
                ],
                FinanceConversation.STATES["INPUT_DATE"]: [
                    CallbackQueryHandler(self.__input_budget_group, pattern="^calendar-date="),
                    self.__calendar_c.create_conversation(
                        pattern="gen-calendar",
                        control_state=FinanceConversation.STATES["CALENDAR_CONTROL"],
                        end_state=FinanceConversation.STATES["CALENDAR_END_CONTROL"],
                        after_conv_state=FinanceConversation.STATES["INPUT_DATE"],
                        fallback_func=self.cancel,
                    )
                ],
                FinanceConversation.STATES["INPUT_BUDGET_GROUP"]: [
                    CallbackQueryHandler(self.__input_budget_type, pattern="^budget-group=")
                ],
                FinanceConversation.STATES["INPUT_BUDGET_TYPE"]: [
                    CallbackQueryHandler(self.__input_description, pattern="^budget-type=")
                ],
                FinanceConversation.STATES["INPUT_DESCRIPTION"]: [
                    MessageHandler(filters.Regex(".*"), self.__input_amount)
                ],
                FinanceConversation.STATES["INPUT_AMOUNT"]: [
                    CallbackQueryHandler(self.__input_confirmation, pattern="^numpad-amount="),
                    self.__numpad_c.create_conversation(
                        pattern="gen-numpad",
                        control_state=FinanceConversation.STATES["NUMPAD_CONTROL"],
                        end_state=FinanceConversation.STATES["NUMPAD_END_CONTROL"],
                        after_conv_state=FinanceConversation.STATES["INPUT_AMOUNT"],
                        fallback_func=self.cancel,
                    )
                ],
                FinanceConversation.STATES["INPUT_CONFIRMATION"]: [
                    CallbackQueryHandler(self.__echo, pattern="^confirm=")
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel)
            ]
        )
        return conv_handler


    # Handler
    async def __start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Starting Finance conversation
        """
        inline_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Create", callback_data="command=create")],
        ])

        await update.message.reply_text(
            text = self.__reply_h.render_text(self.__template_dir, "base_init"),
            parse_mode=ParseMode.HTML,
            reply_markup=inline_keyboard,
        )
        return FinanceConversation.STATES["INPUT_ACTION"]


    async def __input_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        
        command = query.data.split("=")[1]
        context.user_data["command"] = command
        context.user_data["data"] = []

        # TMP
        inline_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Today", callback_data=f"calendar-date={datetime.now(self.__tz).strftime('%Y-%m-%d')}")],
            [InlineKeyboardButton("Choose Date", callback_data=f"gen-calendar")]
        ])
        
        await query.answer()
        await query.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input",
                {
                    **context.user_data,
                    "params": "date",
                }
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=inline_keyboard
        )

        return FinanceConversation.STATES["INPUT_DATE"]


    async def __input_budget_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # Answer Callback
        query = update.callback_query
        await query.answer()

        # Parse Callback
        date_str = query.data.split("=")[1]
        context.user_data["data"].append({"key": "date", "label": "Date", "value": date_str})

        # Get Dim Data
        budget_groups = await self.__usecase.budget_usecase.get_groups()
        inline_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(bg.budget_group, callback_data=f"budget-group={bg.id};'{bg.budget_group}'")]
            for bg in budget_groups
        ])

        await query.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input_exists",
                {
                    **context.user_data,
                    "params": "budget group",
                }
            ),
            parse_mode = ParseMode.HTML,
            reply_markup = inline_keyboard
        )

        return FinanceConversation.STATES["INPUT_BUDGET_GROUP"]
    

    async def __input_budget_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # Answer Callback
        query = update.callback_query
        await query.answer()
        
        # Parse Callback
        budget_group_callback = query.data.split("=")[1]
        budget_group_id, budget_group = budget_group_callback.split(";")
        budget_group_id = int(budget_group_id)
        budget_group = budget_group.replace("'", "")
        context.user_data["data"].append({"key": "budget-group", "label": "Budget Group", "value": budget_group, "id": budget_group_id})
        
        # Get Dim Data
        budget_types = await self.__usecase.budget_usecase.get_types_by_group(budget_group_id)
        inline_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(bt.budget_type, callback_data=f"budget-type={bt.id};'{bt.budget_type}'")]
            for bt in budget_types
        ])

        await query.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input_exists",
                {
                    **context.user_data,
                    "params": "budget type",
                }
            ),
            parse_mode = ParseMode.HTML,
            reply_markup = inline_keyboard
        )

        return FinanceConversation.STATES["INPUT_BUDGET_TYPE"]


    async def __input_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # Answer Callback
        query = update.callback_query
        await query.answer()
        
        # Parse Callback
        budget_type_callback = query.data.split("=")[1]
        budget_type_id, budget_type = budget_type_callback.split(";")
        budget_type_id = int(budget_type_id)
        budget_type = budget_type.replace("'", "")
        context.user_data["data"].append({"key": "budget-type", "label": "Budget Type", "id": budget_type_id, "value": budget_type})

        await query.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input_exists",
                {
                    **context.user_data,
                    "params": "description",
                }
            ),
            parse_mode = ParseMode.HTML,
        )

        context.user_data["chat_id"] = update.effective_chat.id
        context.user_data["last_message_id"] = query.message.message_id
        return FinanceConversation.STATES["INPUT_DESCRIPTION"]
    

    async def __input_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        description = update.message.text
        context.user_data["data"].append({"key": "description", "label": "Description", "value": description})

        # TMP
        inline_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Custom Amount", callback_data=f"gen-numpad")],
        ])

        await context.bot.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input_exists",
                {
                    **context.user_data,
                    "params": "amount",
                }
            ),
            parse_mode = ParseMode.HTML,
            reply_markup = inline_keyboard,
            chat_id = context.user_data["chat_id"],
            message_id = context.user_data["last_message_id"],
        )

        return FinanceConversation.STATES["INPUT_AMOUNT"]
    

    async def __input_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query

        amount = query.data.split("=")[1]
        context.user_data["data"].append({"key": "amount", "label": "Amount", "value": amount})
        
        inline_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes", callback_data=f"confirm=yes"),
                InlineKeyboardButton("No", callback_data=f"confirm=no")
            ]
        ])

        await query.answer()
        await query.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input_confirmation",
                {
                    **context.user_data,
                }
            ),
            parse_mode = ParseMode.HTML,
            reply_markup = inline_keyboard
        )

        return FinanceConversation.STATES["INPUT_CONFIRMATION"]
    

    async def __echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        
        confirm = query.data.split("=")[1]
        context.user_data["confirm"] = confirm

        await query.answer()
        await query.edit_message_text(
            text = self.__reply_h.render_text(
                self.__template_dir,
                "base_input_confirmation",
                {
                    **context.user_data,
                }
            ),
            parse_mode=ParseMode.HTML,
        )

        return ConversationHandler.END


    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancels and ends the conversation."""
        user = update.message.from_user
        await update.message.reply_text(
            "Bye! I hope we can talk again some day."
        )

        return ConversationHandler.END
