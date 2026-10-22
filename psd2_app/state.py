"""Session state for the Reflex PSD2 simulator."""

import asyncio
import json
from datetime import datetime

import reflex as rx

from psd2_app.logic import (
    CONSENT_SCOPES,
    account_currency,
    account_detail_fields,
    account_iban,
    account_id,
    auth_codes_view,
    authorize_and_exchange,
    authorize_tpp_user,
    exchange_authorization_code,
    latest_valid_auth_code,
    login_user_to_ib,
    build_payment_body,
    check_token_status,
    client_choices,
    config_view,
    consents_view,
    create_consent,
    create_payment,
    dashboard_view,
    delete_consent_by_id,
    delete_user_record,
    delete_consents,
    delete_registration,
    describe_consent,
    describe_registration,
    describe_token,
    environment_names,
    account_payment_records,
    balance_entries,
    extract_json,
    is_service_unavailable,
    fetch_balance,
    fetch_consents,
    fetch_otp_codes,
    fetch_transactions,
    otp_result_items,
    get_current_environment,
    load_created_payments,
    payment_table,
    prepare_accounts,
    pretty,
    register_tpp,
    registrations_view,
    response_http_status,
    run_introspection,
    run_payment_action,
    run_revocation,
    save_config_record,
    save_created_payment,
    save_missing_user_accounts,
    creditor_account_choices,
    delete_local_payment,
    save_user_record,
    switch_saved_environment,
    tokens_view,
    transaction_records,
    transaction_total,
    transaction_rows,
    user_choices,
    users_view,
)


TX_PAGE_SIZE = 10
PAGE_WAIT_MESSAGES = {
    "dashboard": "Loading dashboard...",
    "accounts": "Loading accounts...",
    "registrations": "Loading registrations...",
    "users": "Loading users...",
    "tokens": "Loading tokens...",
    "consents": "Loading consents...",
    "configuration": "Loading configuration...",
    "auth-code": "Loading authorization codes...",
}
_TX_BLANK = {
    "index": "",
    "amount": "",
    "currency": "",
    "creditDebitIndicator": "",
    "status": "",
    "bookingDate": "",
    "valueDate": "",
    "counterparty": "",
    "counterpartyName": "",
    "identification": "",
    "tone": "",
    "note": "",
    "detail": "",
    "blank": "1",
}
_PAY_BLANK = {
    "index": "",
    "instructionIdentification": "",
    "transactionIdentification": "",
    "amount": "",
    "requestedExecutionDate": "",
    "dateCreated": "",
    "status": "",
    "tone": "",
    "code": "",
    "instructionPriority": "",
    "signId": "",
    "debtorAccountId": "",
    "debtorIban": "",
    "creditorIban": "",
    "partyId": "",
    "detail": "",
    "blank": "1",
}


class AppState(rx.State):
    environment_options: list[str] = ["ITG", "TST", "PRE", "PROD"]
    current_environment: str = "ITG"
    environment_picker_open: bool = False
    environment_query: str = ""
    client_options: list[str] = ["None"]
    user_options: list[str] = ["None"]
    selected_client_label: str = "None"
    selected_user_label: str = "None"
    selected_client_id: str = ""
    selected_client_name: str = ""
    selected_user_id: str = ""
    selected_user_name: str = ""
    client_picker_open: bool = False
    user_picker_open: bool = False
    client_query: str = ""
    user_query: str = ""

    current_page: str = "dashboard"
    page_loading: bool = False
    page_loading_message: str = ""
    nav_seq: int = 0
    log_open: bool = False
    notice: str = ""
    notice_level: str = "info"
    notice_token: int = 0
    busy: bool = False
    busy_message: str = ""

    dashboard_registration_count: str = "0"
    dashboard_user_count: str = "0"
    dashboard_account_count: str = "0"
    dashboard_payment_count: str = "0"

    user_rows: list[list[str]] = []
    user_labels: list[str] = []
    user_payloads: list[str] = []
    user_detail_label: str = ""
    user_detail_json: str = ""
    user_edit_mode: bool = False
    user_edit_label: str = ""
    form_party_id: str = ""
    form_name: str = ""
    form_birth_date: str = ""
    form_username: str = ""
    form_password: str = ""
    form_phone: str = ""
    form_mpin: str = ""
    user_cards: list[dict[str, str]] = []
    user_query: str = ""
    user_detail_open: bool = False
    user_form_open: bool = False
    user_delete_open: bool = False
    user_detail_index: str = ""
    user_detail_name: str = ""
    user_detail_party_id: str = ""
    user_detail_birth: str = ""
    user_detail_username: str = ""
    user_detail_password: str = ""
    user_detail_phone: str = ""
    user_detail_mpin: str = ""
    user_auth_code: str = ""
    user_auth_code_status: str = ""
    user_auth_code_state: str = ""
    user_auth_code_client: str = ""
    user_otp_open: bool = False
    user_otp_loading: bool = False
    user_otp_error: str = ""
    user_otp_items: list[dict[str, str]] = []
    user_otp_seq: int = 0

    form_config_party_id: str = ""
    form_config_party_name: str = ""
    form_config_party_label: str = ""
    form_config_client_id: str = ""
    form_config_client_name: str = ""
    form_config_client_oauth: str = ""
    form_config_client_label: str = ""
    form_config_redirect_uri: str = ""
    form_config_account_mode: str = "carousel"
    config_json: str = ""
    config_user_picker_open: bool = False
    config_user_query: str = ""
    config_client_picker_open: bool = False
    config_client_query: str = ""

    auth_code_cards: list[dict[str, str]] = []
    auth_code_query: str = ""
    auth_code_detail_open: bool = False
    auth_code_detail_index: str = ""
    auth_code_detail_tpp: str = ""
    auth_code_detail_user: str = ""
    auth_code_detail_user_id: str = ""
    auth_code_detail_scope: str = ""
    auth_code_detail_state: str = ""
    auth_code_detail_code: str = ""
    auth_code_detail_redirect: str = ""
    auth_code_detail_status: str = ""
    auth_code_detail_expires: str = ""
    auth_code_detail_created: str = ""
    auth_code_detail_client_id: str = ""

    registration_count: str = "0"
    registration_rows: list[list[str]] = []
    registration_labels: list[str] = []
    registration_payloads: list[str] = []
    registration_label: str = ""
    registration_client_id: str = ""
    registration_client_secret: str = ""
    registration_access_token: str = ""
    registration_basic_auth: str = ""
    registration_meta: str = ""
    registration_json: str = ""
    registration_raw_client_id: str = ""
    form_registration_name: str = ""
    form_registration_scope: str = "aisp"
    registration_output: str = ""
    registration_template_json: str = ""
    delete_registration_label: str = ""
    registration_cards: list[dict[str, str]] = []
    registration_query: str = ""
    registration_detail_open: bool = False
    registration_create_open: bool = False
    registration_delete_open: bool = False
    registration_name: str = ""
    registration_scope: str = ""
    registration_registered: str = ""
    registration_redirect: str = ""
    registration_grants: str = ""
    registration_auth_method: str = ""

    token_count_label: str = ""
    token_filter_info: str = ""
    token_rows: list[list[str]] = []
    token_labels: list[str] = []
    token_payloads: list[str] = []
    token_label: str = ""
    token_access: str = ""
    token_refresh: str = ""
    token_meta: str = ""
    token_parsed: str = ""
    token_json: str = ""
    token_client_id: str = ""
    token_cards: list[dict[str, str]] = []
    token_query: str = ""
    token_detail_open: bool = False
    token_detail_index: str = ""
    token_detail_tpp: str = ""
    token_detail_user: str = ""
    token_detail_user_id: str = ""
    token_detail_scope: str = ""
    token_detail_access: str = ""
    token_detail_created: str = ""
    token_detail_refresh_created: str = ""
    token_detail_expires: str = ""
    token_action_type: str = "Access"
    token_revoke_open: bool = False
    introspect_label: str = ""
    introspect_type: str = "Access Token"
    introspect_summary: str = ""
    introspect_json: str = ""
    revoke_label: str = ""
    revoke_type: str = "Access Token"

    consent_count_label: str = ""
    consent_filter_info: str = ""
    consent_empty_message: str = ""
    consent_rows: list[list[str]] = []
    consent_labels: list[str] = []
    consent_payloads: list[str] = []
    consent_label: str = ""
    consent_summary: str = ""
    consent_meta: str = ""
    consent_json: str = ""
    consent_cards: list[dict[str, str]] = []
    consent_query: str = ""
    consent_detail_open: bool = False
    consent_status: str = ""
    consent_status_text: str = ""
    consent_detail_id: str = ""
    consent_detail_owner: str = ""
    consent_detail_owner_id: str = ""
    consent_detail_client: str = ""
    consent_detail_client_id: str = ""
    consent_detail_scopes: str = ""
    consent_detail_disponents: str = ""
    consent_detail_valid_from: str = ""
    consent_detail_valid_to: str = ""
    consent_detail_recalled: str = ""
    form_owner_id: str = ""
    form_oauth_client_id: str = ""
    form_oauth_client_name: str = ""
    form_disponent_ids: str = ""
    scope_balance: bool = True
    scope_account_list: bool = True
    scope_transactions: bool = True
    scope_payment: bool = True
    consent_output: str = ""
    form_delete_user_id: str = ""
    form_delete_client_id: str = ""
    form_delete_consent_id: str = ""

    account_logs: list[dict[str, str]] = []
    refresh_error: str = ""
    account_status: str = ""
    account_status_text: str = ""
    account_rows: list[list[str]] = []
    account_labels: list[str] = []
    account_payloads: list[str] = []
    account_cards: list[dict[str, str]] = []
    account_carousel_index: int = 0
    account_list_mode: str = "carousel"
    account_table_query: str = ""
    account_detail_open: bool = False
    account_detail_name: str = ""
    account_detail_product: str = ""
    account_detail_iban: str = ""
    account_detail_number: str = ""
    account_detail_currency: str = ""
    account_detail_id: str = ""
    account_detail_bank: str = ""
    account_detail_bic: str = ""
    account_detail_country: str = ""
    account_detail_owner: str = ""
    account_detail_gradient: str = ""
    account_balances: list[dict[str, str]] = []
    account_balance_note: str = ""
    account_json: str = ""
    account_output: str = ""
    tx_account_label: str = ""
    tx_page: str = "0"
    tx_size: str = "100"
    tx_rows: list[list[str]] = []
    tx_records: list[dict[str, str]] = []
    tx_page_index: int = 0
    tx_total: int = -1
    tx_selected_index: str = ""
    tx_detail_open: bool = False
    tx_fullscreen: bool = False
    tx_json: str = ""
    tx_output: str = ""
    pay_account_label: str = ""
    pay_instruction_id: str = ""
    pay_priority: str = "NORM"
    pay_amount: str = "999.99"
    pay_currency: str = "CZK"
    pay_date: str = "2026-05-25"
    pay_debtor_iban: str = "CZ5622500000004121931301"
    pay_creditor_iban: str = ""
    pay_creditor_label: str = ""
    pay_creditor_options: list[str] = []
    pay_creditor_currency: str = "CZK"
    pay_unstructured: str = "Zpráva pro příjemce platby"
    pay_vs: str = "7418529630"
    pay_ss: str = "1234567890"
    pay_ks: str = "0308"
    pay_note_requestor: str = "Zaplatil jsem kamarádovi."
    pay_note_bank: str = "Text zprávy pro banku"
    pay_narrative: str = "Další komentáře k transakci"
    pay_request_json: str = ""
    pay_response_json: str = ""
    pay_output: str = ""
    payment_rows: list[list[str]] = []
    payment_labels: list[str] = []
    payment_label: str = ""
    payment_action_output: str = ""
    account_payment_records: list[dict[str, str]] = []
    pay_page_index: int = 0
    pay_selected_index: str = ""
    pay_detail_open: bool = False
    pay_action_output: str = ""
    pay_form_open: bool = False
    pay_edit_index: str = ""

    @rx.var
    def carousel_at_start(self) -> bool:
        return self.account_carousel_index <= 0

    @rx.var
    def carousel_at_end(self) -> bool:
        return self.account_carousel_index >= max(len(self.account_cards) - 1, 0)

    @rx.var
    def account_carousel_label(self) -> str:
        if not self.account_cards:
            return ""
        return f"{self.account_carousel_index + 1} / {len(self.account_cards)}"

    def _card_at(self, index: int) -> dict[str, str]:
        empty = {"index": "", "name": "", "iban": "", "currency": "", "id": "", "gradient": "transparent"}
        if index < 0 or index >= len(self.account_cards):
            return empty
        return self.account_cards[index]

    @rx.var
    def center_card(self) -> dict[str, str]:
        return self._card_at(self.account_carousel_index)

    @rx.var
    def left_card(self) -> dict[str, str]:
        return self._card_at(self.account_carousel_index - 1)

    @rx.var
    def right_card(self) -> dict[str, str]:
        return self._card_at(self.account_carousel_index + 1)

    @rx.var
    def has_left_card(self) -> bool:
        return len(self.account_cards) > 2 and self.account_carousel_index > 0

    @rx.var
    def has_right_card(self) -> bool:
        return len(self.account_cards) > 2 and self.account_carousel_index < len(self.account_cards) - 1

    @rx.var
    def carousel_slots(self) -> list[dict[str, str]]:
        cards = self.account_cards
        count = len(cards)
        if count == 0:
            return []
        if count <= 2:
            return [{**card, "kind": "same"} for card in cards]
        index = min(max(self.account_carousel_index, 0), count - 1)
        slots = []
        if index > 0:
            slots.append({**cards[index - 1], "kind": "side"})
        slots.append({**cards[index], "kind": "large"})
        if index < count - 1:
            slots.append({**cards[index + 1], "kind": "side"})
        return slots

    @rx.var
    def available_balance_amount(self) -> str:
        for item in self.account_balances:
            if item.get("role") == "available":
                return item.get("amount") or ""
        return ""

    @rx.var
    def other_balances(self) -> list[dict[str, str]]:
        return [item for item in self.account_balances if item.get("role") != "available"]

    @rx.var
    def tx_page_rows(self) -> list[dict[str, str]]:
        rows = list(self.tx_records)
        while len(rows) < TX_PAGE_SIZE:
            rows.append(dict(_TX_BLANK))
        return rows[:TX_PAGE_SIZE]

    @rx.var
    def tx_page_label(self) -> str:
        current = self.tx_page_index + 1
        if self.tx_total < 0:
            return str(current)
        pages = max(1, (self.tx_total + TX_PAGE_SIZE - 1) // TX_PAGE_SIZE)
        return f"{current} / {pages}"

    @rx.var
    def tx_has_prev(self) -> bool:
        return self.tx_page_index > 0

    @rx.var
    def tx_has_next(self) -> bool:
        if self.tx_total >= 0:
            return (self.tx_page_index + 1) * TX_PAGE_SIZE < self.tx_total
        return len(self.tx_records) >= TX_PAGE_SIZE

    @rx.var
    def selected_tx(self) -> dict[str, str]:
        for record in self.tx_records:
            if self.tx_selected_index and record.get("index") == self.tx_selected_index:
                return record
        return dict(_TX_BLANK)

    @rx.var
    def pay_page_rows(self) -> list[dict[str, str]]:
        start = self.pay_page_index * TX_PAGE_SIZE
        rows = list(self.account_payment_records[start:start + TX_PAGE_SIZE])
        while len(rows) < TX_PAGE_SIZE:
            rows.append(dict(_PAY_BLANK))
        return rows

    @rx.var
    def pay_page_label(self) -> str:
        pages = max(1, (len(self.account_payment_records) + TX_PAGE_SIZE - 1) // TX_PAGE_SIZE)
        current = min(self.pay_page_index, pages - 1) + 1
        return f"{current} / {pages}"

    @rx.var
    def pay_has_prev(self) -> bool:
        return self.pay_page_index > 0

    @rx.var
    def pay_has_next(self) -> bool:
        return (self.pay_page_index + 1) * TX_PAGE_SIZE < len(self.account_payment_records)

    @rx.var
    def selected_payment(self) -> dict[str, str]:
        for record in self.account_payment_records:
            if self.pay_selected_index and record.get("index") == self.pay_selected_index:
                return record
        return dict(_PAY_BLANK)

    @rx.var
    def payment_can_authorize(self) -> bool:
        for record in self.account_payment_records:
            if self.pay_selected_index and record.get("index") == self.pay_selected_index:
                return bool(record.get("signId")) and record.get("status") in {"AUTHORIZATION_REQUIRED", "ACCP"}
        return False

    @rx.var
    def payment_can_delete(self) -> bool:
        for record in self.account_payment_records:
            if self.pay_selected_index and record.get("index") == self.pay_selected_index:
                return record.get("status") in {"ACCP", "AUTHORIZATION_REQUIRED", "OPEN"}
        return False

    @rx.var
    def filtered_client_options(self) -> list[str]:
        query = self.client_query.strip().lower()
        if not query:
            return self.client_options
        return [item for item in self.client_options if query in item.lower()]

    @rx.var
    def filtered_user_options(self) -> list[str]:
        query = self.user_query.strip().lower()
        if not query:
            return self.user_options
        return [item for item in self.user_options if query in item.lower()]

    @rx.var
    def filtered_config_user_options(self) -> list[str]:
        query = self.config_user_query.strip().lower()
        items = [item for item in self.user_options if item != "None"]
        if not query:
            return items
        return [item for item in items if query in item.lower()]

    @rx.var
    def filtered_config_client_options(self) -> list[str]:
        query = self.config_client_query.strip().lower()
        items = [item for item in self.client_options if item != "None"]
        if not query:
            return items
        return [item for item in items if query in item.lower()]

    @rx.var
    def filtered_environment_options(self) -> list[str]:
        query = self.environment_query.strip().lower()
        if not query:
            return self.environment_options
        return [item for item in self.environment_options if query in item.lower()]

    @rx.var
    def context_line(self) -> str:
        parts = []
        if self.selected_client_name:
            parts.append(self.selected_client_name)
        if self.selected_user_id:
            parts.append(f"{self.selected_user_name} ({self.selected_user_id})")
        return " · ".join(parts)

    @rx.var
    def selected_scopes(self) -> list[str]:
        scopes = []
        if self.scope_balance:
            scopes.append(CONSENT_SCOPES[0])
        if self.scope_account_list:
            scopes.append(CONSENT_SCOPES[1])
        if self.scope_transactions:
            scopes.append(CONSENT_SCOPES[2])
        if self.scope_payment:
            scopes.append(CONSENT_SCOPES[3])
        return scopes

    def _log(self, message: str, level: str = "info"):
        color = {"error": "red", "warning": "orange", "success": "green"}.get(level, "blue")
        self.account_logs = [
            *self.account_logs,
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": message,
                "color": color,
            },
        ]
        if len(self.account_logs) > 80:
            self.account_logs = self.account_logs[-80:]

    def _notify(self, message: str, level: str = "info"):
        self.notice = message
        self.notice_level = level
        self.notice_token += 1
        self._log(message, level)
        if level == "error":
            return AppState.schedule_clear_critical
        if level == "warning":
            return AppState.schedule_clear_warning
        return AppState.schedule_clear_info

    @rx.event(background=True)
    async def schedule_clear_critical(self):
        async with self:
            token = self.notice_token
        await asyncio.sleep(5)
        async with self:
            if self.notice_token == token and self.notice_level == "error":
                self.notice = ""

    @rx.event(background=True)
    async def schedule_clear_warning(self):
        async with self:
            token = self.notice_token
        await asyncio.sleep(12)
        async with self:
            if self.notice_token == token and self.notice_level == "warning":
                self.notice = ""

    @rx.event(background=True)
    async def schedule_clear_info(self):
        async with self:
            token = self.notice_token
        await asyncio.sleep(5)
        async with self:
            if self.notice_token == token and self.notice_level in ("info", "success"):
                self.notice = ""

    @rx.event
    def toggle_log(self):
        self.log_open = not self.log_open

    def _arm_page_wait(self) -> tuple[int, str]:
        self.nav_seq += 1
        page_id = self.current_page or "dashboard"
        self.page_loading = True
        self.page_loading_message = PAGE_WAIT_MESSAGES.get(page_id, "Loading...")
        return self.nav_seq, page_id

    async def _finish_page_load(self, page_id: str, seq: int):
        # Let the blur and spinner paint before a fast local reload finishes.
        await asyncio.sleep(0.15)
        try:
            await self._load_page(page_id, seq)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with self:
                if self.nav_seq == seq:
                    self._notify(f"Failed to open page: {exc}", "error")
        finally:
            async with self:
                if self.nav_seq == seq:
                    self.page_loading = False

    @rx.event(background=True)
    async def show_page(self, page_id: str):
        async with self:
            self.notice = ""
            self.current_page = page_id
            seq, page_id = self._arm_page_wait()
        await self._finish_page_load(page_id, seq)

    async def _load_page(self, page_id: str, seq: int):
        if page_id == "accounts":
            await self._load_accounts_for_nav(seq)
            return
        if page_id == "tokens":
            await self._load_tokens_for_nav(seq)
            return
        if page_id == "consents":
            await self._load_consents_for_nav(seq)
            return
        async with self:
            if self.nav_seq != seq:
                return
            if page_id == "registrations":
                self.open_registrations()
            elif page_id == "users":
                self.open_users()
            elif page_id == "configuration":
                self.open_configuration()
            elif page_id == "auth-code":
                self.open_auth_codes()
            else:
                self.open_dashboard()

    async def _load_accounts_for_nav(self, seq: int):
        async with self:
            if self.nav_seq != seq:
                return
            self.refresh_sidebar_options()
            self._apply_account_list_mode()
            if not self.selected_client_id or not self.selected_user_id:
                self.account_status = "missing_context"
                self.account_rows = []
                self.account_labels = []
                self.account_cards = []
                self.account_detail_open = False
                self._notify("Select both Application and User in the sidebar.", "warning")
                return
            if self.notice == "Select both Application and User in the sidebar.":
                self.notice = ""
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            self.account_cards = []
            self.account_rows = []
            self.account_detail_open = False
        data = await prepare_accounts(client_id, user_id)
        async with self:
            if self.nav_seq != seq:
                return
            self._apply_account_view(data)

    async def _load_tokens_for_nav(self, seq: int):
        async with self:
            if self.nav_seq != seq:
                return
            self.refresh_sidebar_options()
            self.token_detail_open = False
            self.token_revoke_open = False
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            previous = self.token_label
        try:
            data = await asyncio.to_thread(tokens_view, client_id, user_id)
        except Exception as exc:
            async with self:
                if self.nav_seq == seq:
                    self._notify(f"Failed to load tokens: {exc}", "error")
            return
        async with self:
            if self.nav_seq != seq:
                return
            self._apply_token_data(data, previous)

    async def _load_consents_for_nav(self, seq: int):
        async with self:
            if self.nav_seq != seq:
                return
            self.refresh_sidebar_options()
            self.form_owner_id = self.selected_user_id
            self.form_oauth_client_id = self.selected_client_id
            self.form_disponent_ids = self.selected_user_id
            self.form_delete_user_id = self.selected_user_id
            self.form_delete_client_id = self.selected_client_id
            self.consent_detail_open = False
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            if not client_id and not user_id:
                self._clear_consents("missing_context")
                return
            self.consent_cards = []
        consents, error = await asyncio.to_thread(fetch_consents, client_id, user_id)
        async with self:
            if self.nav_seq != seq:
                return
            if consents is None:
                self._fail_consents(error)
                return
            self._apply_consents(consents)

    def _apply_account_list_mode(self):
        self.account_list_mode = config_view()["account_list_mode"]

    def _saved_user(self, party_id: str) -> tuple[str, str, str]:
        wanted = str(party_id or "").strip()
        if not wanted:
            return "", "", ""
        for label, saved_party_id, name in user_choices():
            if saved_party_id == wanted:
                return label, saved_party_id, name
        return "", wanted, ""

    def _apply_saved_context(self):
        self.refresh_sidebar_options()
        data = config_view()
        self.account_list_mode = data["account_list_mode"]
        label, _party_id, _name = self._saved_user(data["party_id"])
        if label:
            self._apply_user(label)
        client_key = data["client_id"]
        for choice, client_id, name in client_choices():
            if client_key and (name == client_key or client_id == client_key):
                self._apply_client(choice)
                break

    @rx.event(background=True)
    async def boot(self):
        async with self:
            self._apply_saved_context()
            seq, page_id = self._arm_page_wait()
        await self._finish_page_load(page_id, seq)

    def refresh_sidebar_options(self):
        self.environment_options = environment_names() or ["ITG", "TST", "PRE", "PROD"]
        self.current_environment = get_current_environment()
        clients = client_choices()
        users = user_choices()
        self.client_options = ["None"] + [label for label, _client_id, _name in clients]
        self.user_options = ["None"] + [label for label, _party_id, _name in users]
        if self.selected_client_label not in self.client_options:
            self.selected_client_label = "None"
            self.selected_client_id = ""
            self.selected_client_name = ""
        if self.selected_user_label not in self.user_options:
            self.selected_user_label = "None"
            self.selected_user_id = ""
            self.selected_user_name = ""

    def _apply_client(self, label: str):
        self.selected_client_label = label or "None"
        self.selected_client_id = ""
        self.selected_client_name = ""
        for choice, client_id, name in client_choices():
            if choice == label:
                self.selected_client_id = client_id
                self.selected_client_name = name
                break

    def _apply_user(self, label: str):
        self.selected_user_label = label or "None"
        self.selected_user_id = ""
        self.selected_user_name = ""
        for choice, party_id, name in user_choices():
            if choice == label:
                self.selected_user_id = party_id
                self.selected_user_name = name
                break

    @rx.event
    def set_client_picker_open(self, is_open: bool):
        self.client_picker_open = is_open
        if is_open:
            self.client_query = ""

    @rx.event
    def set_user_picker_open(self, is_open: bool):
        self.user_picker_open = is_open
        if is_open:
            self.user_query = ""

    @rx.event(background=True)
    async def select_client(self, label: str):
        async with self:
            self.client_picker_open = False
            self.client_query = ""
            self._apply_client(label)
            self.notice = ""
            seq, page_id = self._arm_page_wait()
        await self._finish_page_load(page_id, seq)

    @rx.event(background=True)
    async def select_user(self, label: str):
        async with self:
            self.user_picker_open = False
            self.user_query = ""
            self._apply_user(label)
            self.notice = ""
            seq, page_id = self._arm_page_wait()
        await self._finish_page_load(page_id, seq)

    @rx.event
    def set_environment_picker_open(self, is_open: bool):
        self.environment_picker_open = is_open
        if is_open:
            self.environment_query = ""

    @rx.event(background=True)
    async def switch_environment(self, environment: str):
        async with self:
            self.environment_picker_open = False
            self.environment_query = ""
            if not environment or environment == self.current_environment:
                return
            try:
                self.current_environment = switch_saved_environment(environment)
            except Exception as exc:
                self._notify(f"Failed to switch environment: {exc}", "error")
                return
            switched = self.current_environment
            self.selected_client_label = "None"
            self.selected_client_id = ""
            self.selected_client_name = ""
            self.selected_user_label = "None"
            self.selected_user_id = ""
            self.selected_user_name = ""
            self.refresh_sidebar_options()
            self.notice = ""
            seq, page_id = self._arm_page_wait()
        await self._finish_page_load(page_id, seq)
        async with self:
            if self.nav_seq == seq:
                self._notify(f"Switched to {switched}", "success")

    @rx.event
    def open_dashboard(self):
        self.refresh_sidebar_options()
        data = dashboard_view()
        self.dashboard_registration_count = data["registration_count"]
        self.dashboard_user_count = data["user_count"]
        self.dashboard_account_count = data["account_count"]
        self.dashboard_payment_count = data["payment_count"]

    @rx.event
    def open_users(self):
        self.refresh_sidebar_options()
        self.user_detail_open = False
        self.user_form_open = False
        self.user_delete_open = False
        self._load_users()

    def _load_users(self):
        data = users_view()
        self.user_rows = data["rows"]
        self.user_cards = data["cards"]
        self.user_labels = data["labels"]
        self.user_payloads = data["payloads"]
        if self.user_detail_open:
            try:
                selected = int(self.user_detail_index)
            except (TypeError, ValueError):
                selected = -1
            if 0 <= selected < len(self.user_payloads):
                self._apply_user_detail(selected)
            else:
                self.user_detail_open = False
        elif not self.user_labels:
            self.user_detail_label = ""
            self.user_detail_json = ""

    def _apply_user_detail(self, selected: int):
        user = json.loads(self.user_payloads[selected])
        self.user_detail_index = str(selected)
        self.user_detail_label = self.user_labels[selected] if selected < len(self.user_labels) else ""
        self.user_detail_json = self.user_payloads[selected]
        self.user_detail_name = str(user.get("name") or "Unknown")
        self.user_detail_party_id = str(user.get("partyId") or "")
        self.user_detail_birth = str(user.get("birthDate") or "")
        self.user_detail_username = str(user.get("username") or "")
        self.user_detail_password = str(user.get("password") or "")
        self.user_detail_phone = str(user.get("phoneNumber") or "")
        self.user_detail_mpin = str(user.get("mpin") or "")
        self._load_user_auth_code()

    def _load_user_auth_code(self):
        found = latest_valid_auth_code(self.user_detail_party_id, self.selected_client_id)
        if not found:
            self.user_auth_code = ""
            self.user_auth_code_status = ""
            self.user_auth_code_state = ""
            self.user_auth_code_client = ""
            return
        self.user_auth_code = found["code"]
        self.user_auth_code_status = found["status"]
        self.user_auth_code_state = found["state"]
        self.user_auth_code_client = found["client_id"]

    def _fill_user_form(self, user: dict | None):
        user = user or {}
        self.form_party_id = str(user.get("partyId") or "")
        self.form_name = str(user.get("name") or "")
        self.form_birth_date = str(user.get("birthDate") or "")
        self.form_username = str(user.get("username") or "")
        self.form_password = str(user.get("password") or "")
        self.form_phone = str(user.get("phoneNumber") or "")
        self.form_mpin = str(user.get("mpin") or "")

    @rx.event
    def show_user(self, label: str):
        self.user_detail_label = label
        if label in self.user_labels:
            selected = self.user_labels.index(label)
            self.user_detail_json = self.user_payloads[selected]
            self._apply_user_detail(selected)

    @rx.event
    def open_user_detail(self, index: str):
        try:
            selected = int(index)
        except (TypeError, ValueError):
            return
        if selected < 0 or selected >= len(self.user_payloads):
            return
        self._apply_user_detail(selected)
        self.user_detail_open = True
        self._close_user_otp()

    def _close_user_otp(self):
        self.user_otp_open = False
        self.user_otp_loading = False
        self.user_otp_error = ""
        self.user_otp_items = []
        self.user_otp_seq += 1

    @rx.event
    def close_user_detail(self):
        self.user_detail_open = False
        self.user_form_open = False
        self.user_delete_open = False
        self._close_user_otp()

    @rx.event
    def open_create_user(self):
        self.user_edit_mode = False
        self.user_edit_label = ""
        self._fill_user_form(None)
        self.user_form_open = True

    @rx.event
    def open_edit_user(self):
        try:
            selected = int(self.user_detail_index)
        except (TypeError, ValueError):
            return
        if selected < 0 or selected >= len(self.user_payloads):
            return
        self.user_edit_mode = True
        self.user_edit_label = self.user_detail_label
        self._fill_user_form(json.loads(self.user_payloads[selected]))
        self.user_form_open = True

    @rx.event
    def open_user_delete(self):
        if self.user_detail_index == "":
            self._notify("Select a user to delete.", "warning")
            return
        self.user_delete_open = True

    @rx.var
    def filtered_user_cards(self) -> list[dict[str, str]]:
        query = self.user_query.strip().lower()
        if not query:
            return self.user_cards
        matched = []
        for card in self.user_cards:
            blob = " ".join(str(card.get(field) or "") for field in ("name", "id", "birth", "username", "phone")).lower()
            if query in blob:
                matched.append(card)
        return matched

    @rx.event
    def set_user_edit_mode(self, enabled: bool):
        self.user_edit_mode = bool(enabled)
        if not self.user_edit_mode:
            self._fill_user_form(None)

    @rx.event
    def apply_edit_user(self, label: str):
        self.user_edit_label = label
        if label not in self.user_labels:
            return
        self._fill_user_form(json.loads(self.user_payloads[self.user_labels.index(label)]))

    @rx.event
    def save_user(self):
        form = {
            "partyId": self.form_party_id.strip(),
            "name": self.form_name.strip(),
            "birthDate": self.form_birth_date.strip(),
            "username": self.form_username.strip(),
            "password": self.form_password,
            "phoneNumber": self.form_phone.strip(),
        }
        if self.form_mpin.strip():
            form["mpin"] = self.form_mpin.strip()
        ok, message = save_user_record(self.user_edit_mode, self.user_edit_label, self.user_labels, form)
        self._notify(message, "success" if ok else "error")
        if ok:
            self.user_form_open = False
            self.refresh_sidebar_options()
            self._load_users()

    @rx.event(background=True)
    async def login_open_user(self):
        async with self:
            user_id = self.user_detail_party_id.strip()
            if not user_id:
                self._notify("Select a user first.", "warning")
                return
            self.busy = True
            self.busy_message = "Internet Banking login is running. Complete it in the browser window."
        result = await asyncio.to_thread(login_user_to_ib, user_id)
        async with self:
            self.busy = False
            self._notify(result["message"], "success" if result["ok"] else "warning")

    @rx.event(background=True)
    async def authorize_open_user(self):
        async with self:
            user_id = self.user_detail_party_id.strip()
            client_id = self.selected_client_id.strip()
            if not user_id:
                self._notify("Select a user first.", "warning")
                return
            if not client_id:
                self._notify("Select a TPP in the context first.", "warning")
                return
            self.busy = True
            self.busy_message = "Authorization is running. Complete it in the browser window."
        result = await asyncio.to_thread(authorize_tpp_user, client_id, user_id)
        async with self:
            self.busy = False
            if result["ok"]:
                self._load_user_auth_code()
            self._notify(result["message"], "success" if result["ok"] else "warning")

    @rx.event(background=True)
    async def exchange_open_user_code(self):
        async with self:
            client_id = self.user_auth_code_client.strip()
            user_id = self.user_detail_party_id.strip()
            state = self.user_auth_code_state.strip()
            if not self.user_auth_code.strip() or not client_id or not user_id:
                self._notify("No valid authorization code.", "warning")
                return
            self.busy = True
            self.busy_message = "Exchanging the authorization code for a token."
        result = await asyncio.to_thread(exchange_authorization_code, client_id, user_id, state)
        async with self:
            self.busy = False
            if result["ok"]:
                self.user_auth_code = ""
                self.user_auth_code_status = ""
                self.user_auth_code_state = ""
                self.user_auth_code_client = ""
            self._notify(result["message"], "success" if result["ok"] else "warning")

    @rx.event(background=True)
    async def get_user_otps(self):
        async with self:
            user_id = self.user_detail_party_id.strip()
            if not user_id:
                self._notify("Select a user first.", "warning")
                return
            self.user_otp_seq += 1
            seq = self.user_otp_seq
            self.user_otp_open = True
            self.user_otp_loading = True
            self.user_otp_error = ""
            self.user_otp_items = []
        try:
            codes, error = await asyncio.to_thread(fetch_otp_codes, user_id, 30)
        except Exception as exc:
            codes, error = None, str(exc)
        async with self:
            if self.user_otp_seq != seq:
                return
            self.user_otp_loading = False
            if codes is None:
                self.user_otp_error = error or "Could not fetch OTP codes."
                self.user_otp_items = []
                return
            self.user_otp_items = otp_result_items(codes)

    @rx.event
    def submit_delete_user(self):
        try:
            index = int(self.user_detail_index)
        except (TypeError, ValueError):
            self.user_delete_open = False
            self._notify("Select a user to delete.", "warning")
            return
        ok, message = delete_user_record(index)
        self.user_delete_open = False
        self._notify(message, "success" if ok else "error")
        if ok:
            self.user_detail_open = False
            self.user_detail_index = ""
            self.user_detail_label = ""
            self.refresh_sidebar_options()
            self._load_users()

    def _fill_configuration_form(self, data: dict):
        label, party_id, name = self._saved_user(data["party_id"])
        self.form_config_party_label = label
        self.form_config_party_id = party_id
        self.form_config_party_name = name
        self.form_config_client_id = data["client_id"]
        self.form_config_client_name = data["client_id"]
        self.form_config_client_oauth = ""
        self.form_config_client_label = ""
        for label, client_id, name in client_choices():
            if data["client_id"] and (name == data["client_id"] or client_id == data["client_id"]):
                self.form_config_client_label = label
                self.form_config_client_name = name
                self.form_config_client_oauth = client_id
                self.form_config_client_id = name
                break
        self.form_config_redirect_uri = data["redirect_uri"]
        self.form_config_account_mode = data["account_list_mode"]
        self.config_json = data["json"]

    @rx.event
    def open_configuration(self):
        self.refresh_sidebar_options()
        self._fill_configuration_form(config_view())

    @rx.event
    def set_config_user_picker_open(self, is_open: bool):
        self.config_user_picker_open = is_open
        if is_open:
            self.config_user_query = ""

    @rx.event
    def set_config_client_picker_open(self, is_open: bool):
        self.config_client_picker_open = is_open
        if is_open:
            self.config_client_query = ""

    @rx.event
    def pick_config_user(self, label: str):
        self.config_user_picker_open = False
        self.config_user_query = ""
        self.form_config_party_label = label
        for choice, party_id, name in user_choices():
            if choice == label:
                self.form_config_party_id = party_id
                self.form_config_party_name = name
                break

    @rx.event
    def pick_config_client(self, label: str):
        self.config_client_picker_open = False
        self.config_client_query = ""
        self.form_config_client_label = label
        for choice, client_id, name in client_choices():
            if choice == label:
                self.form_config_client_id = name
                self.form_config_client_name = name
                self.form_config_client_oauth = client_id
                break

    @rx.event
    def set_form_config_account_mode(self, value: str | list[str]):
        mode = value[0] if isinstance(value, list) else value
        if mode in {"carousel", "table"}:
            self.form_config_account_mode = mode

    @rx.event
    def save_configuration(self):
        ok, message = save_config_record(
            self.form_config_party_id,
            self.form_config_client_name or self.form_config_client_id,
            self.form_config_redirect_uri,
            self.form_config_account_mode,
        )
        self._notify(message, "success" if ok else "error")
        if ok:
            self.open_configuration()

    @rx.event
    def open_auth_codes(self):
        self.refresh_sidebar_options()
        self.auth_code_detail_open = False
        data = auth_codes_view(self.selected_client_id, self.selected_user_id)
        self.auth_code_cards = data["cards"]

    @rx.var
    def filtered_auth_code_cards(self) -> list[dict[str, str]]:
        query = self.auth_code_query.strip().lower()
        if not query:
            return self.auth_code_cards
        matched = []
        for card in self.auth_code_cards:
            blob = " ".join(
                str(card.get(field) or "")
                for field in ("tpp", "tpp_id", "user", "user_id", "scope", "state", "expires", "created")
            ).lower()
            if query in blob:
                matched.append(card)
        return matched

    def _apply_auth_code_detail(self, card: dict):
        self.auth_code_detail_index = str(card.get("index") or "")
        self.auth_code_detail_tpp = str(card.get("tpp") or "")
        self.auth_code_detail_user = str(card.get("user") or "")
        self.auth_code_detail_user_id = str(card.get("user_id") or "")
        self.auth_code_detail_scope = str(card.get("scope") or "")
        self.auth_code_detail_state = str(card.get("state") or "")
        self.auth_code_detail_code = str(card.get("code") or "")
        self.auth_code_detail_redirect = str(card.get("redirect") or "")
        self.auth_code_detail_status = str(card.get("status") or "")
        self.auth_code_detail_expires = str(card.get("expires") or "")
        self.auth_code_detail_created = str(card.get("created") or "")
        self.auth_code_detail_client_id = str(card.get("tpp_id") or "")

    @rx.event
    def open_auth_code_detail(self, index: str):
        card = next((item for item in self.auth_code_cards if item.get("index") == str(index)), None)
        if not card:
            return
        self._apply_auth_code_detail(card)
        self.auth_code_detail_open = True

    @rx.event
    def close_auth_code_detail(self):
        self.auth_code_detail_open = False

    @rx.event(background=True)
    async def exchange_selected_auth_code(self):
        async with self:
            client_id = self.auth_code_detail_client_id.strip()
            user_id = self.auth_code_detail_user_id.strip()
            state = self.auth_code_detail_state.strip()
            if not self.auth_code_detail_code.strip() or not client_id or not user_id:
                self._notify("No valid authorization code.", "warning")
                return
            self.busy = True
            self.busy_message = "Exchanging the authorization code for a token."
        result = await asyncio.to_thread(exchange_authorization_code, client_id, user_id, state)
        async with self:
            self.busy = False
            if result["ok"]:
                if self.user_auth_code_state == state:
                    self.user_auth_code = ""
                    self.user_auth_code_status = ""
                    self.user_auth_code_state = ""
                    self.user_auth_code_client = ""
                self.open_auth_codes()
            self._notify(result["message"], "success" if result["ok"] else "warning")

    @rx.event
    def open_registrations(self):
        self.refresh_sidebar_options()
        self.registration_detail_open = False
        self.registration_create_open = False
        self.registration_delete_open = False
        self._load_registrations(fill_form=not self.form_registration_name)

    def _load_registrations(self, fill_form: bool = False):
        data = registrations_view()
        self.registration_count = data["count"]
        self.registration_rows = data["rows"]
        self.registration_cards = data["cards"]
        self.registration_labels = data["labels"]
        self.registration_payloads = data["payloads"]
        self.registration_template_json = data["template_json"]
        if fill_form:
            self.form_registration_name = data["template_name"]
            self.form_registration_scope = data["template_scope"]
        if self.registration_detail_open and self.registration_label in self.registration_labels:
            self.show_registration(self.registration_label)
        elif not self.registration_labels:
            self.registration_label = ""
            self.registration_json = ""
            self.registration_raw_client_id = ""
            self.registration_detail_open = False

    def _apply_registration_details(self, details: dict):
        self.registration_client_id = details["client_id"]
        self.registration_client_secret = details["client_secret"]
        self.registration_access_token = details["access_token"]
        self.registration_basic_auth = details["basic_auth"]
        self.registration_meta = details["meta"]
        self.registration_json = details["json"]
        self.registration_raw_client_id = details["raw_client_id"]
        self.registration_name = details["name"]
        self.registration_scope = details["scope"]
        self.registration_registered = details["registered"]
        self.registration_redirect = details["redirect"]
        self.registration_grants = details["grants"]
        self.registration_auth_method = details["auth_method"]

    @rx.event
    def show_registration(self, label: str):
        self.registration_label = label
        if label not in self.registration_labels:
            return
        details = describe_registration(self.registration_payloads[self.registration_labels.index(label)])
        self._apply_registration_details(details)

    @rx.event
    def open_registration_detail(self, index: str):
        try:
            selected = int(index)
        except (TypeError, ValueError):
            return
        if selected < 0 or selected >= len(self.registration_payloads):
            return
        label = self.registration_labels[selected] if selected < len(self.registration_labels) else ""
        self.registration_label = label
        self._apply_registration_details(describe_registration(self.registration_payloads[selected]))
        self.registration_detail_open = True

    @rx.event
    def close_registration_detail(self):
        self.registration_detail_open = False
        self.registration_delete_open = False

    @rx.event
    def open_create_registration(self):
        if not self.form_registration_name.strip():
            data = registrations_view()
            self.form_registration_name = data["template_name"]
            self.form_registration_scope = data["template_scope"]
        self.registration_create_open = True

    @rx.event
    def open_registration_delete(self):
        if not self.registration_raw_client_id:
            self._notify("Selected registration has no client ID.", "error")
            return
        self.registration_delete_open = True

    @rx.var
    def filtered_registration_cards(self) -> list[dict[str, str]]:
        query = self.registration_query.strip().lower()
        if not query:
            return self.registration_cards
        matched = []
        for card in self.registration_cards:
            blob = " ".join(str(card.get(field) or "") for field in ("name", "id", "scopes", "registered")).lower()
            if query in blob:
                matched.append(card)
        return matched

    @rx.event
    def choose_delete_registration(self, label: str):
        self.delete_registration_label = label

    @rx.event(background=True)
    async def submit_registration(self):
        async with self:
            self.busy = True
            self.busy_message = "Registering TPP..."
            name = self.form_registration_name
            scope = self.form_registration_scope
        result = await asyncio.to_thread(register_tpp, name, scope)
        async with self:
            self.busy = False
            self.registration_output = result["output"]
            self._notify(result["message"], "success" if result["ok"] else "error")
            if result["ok"]:
                self.registration_create_open = False
                self.refresh_sidebar_options()
                self._load_registrations()

    @rx.event(background=True)
    async def submit_delete_registration(self):
        async with self:
            client_id = self.registration_raw_client_id
            if not client_id:
                self.registration_delete_open = False
                self._notify("Selected registration has no client ID.", "error")
                return
            self.registration_delete_open = False
            self.busy = True
            self.busy_message = "Deleting registration..."
        result = await asyncio.to_thread(delete_registration, client_id)
        async with self:
            self.busy = False
            self.registration_output = result["output"]
            self._notify(result["message"], "success" if result["ok"] else "error")
            if result["ok"]:
                self.registration_detail_open = False
                self.registration_label = ""
                self.registration_raw_client_id = ""
                self.refresh_sidebar_options()
                self._load_registrations()

    @rx.event
    def open_tokens(self):
        self.refresh_sidebar_options()
        return AppState.load_tokens

    @rx.event(background=True)
    async def load_tokens(self):
        async with self:
            self.busy = True
            self.busy_message = "Loading tokens..."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            previous = self.token_label
        try:
            data = await asyncio.to_thread(tokens_view, client_id, user_id)
        except Exception as exc:
            async with self:
                self.busy = False
                self._notify(f"Failed to load tokens: {exc}", "error")
            return
        async with self:
            self.busy = False
            self._apply_token_data(data, previous)

    def _apply_token_data(self, data: dict, previous: str):
        self.token_count_label = f"Showing {data['shown']} of {data['total']} tokens"
        self.token_filter_info = data["filter_info"]
        self.token_rows = data["rows"]
        self.token_labels = data["labels"]
        self.token_payloads = data["payloads"]
        self.token_cards = data["cards"]
        self.token_detail_open = False
        self.token_revoke_open = False
        self.introspect_summary = ""
        self.introspect_json = ""
        if self.token_labels:
            label = previous if previous in self.token_labels else self.token_labels[0]
            self.token_label = label
            if self.introspect_label not in self.token_labels:
                self.introspect_label = label
            if self.revoke_label not in self.token_labels:
                self.revoke_label = label
        else:
            self.token_label = ""
            self.token_access = ""
            self.token_refresh = ""
            self.token_meta = ""
            self.token_parsed = ""
            self.token_json = ""
            self.token_client_id = ""

    @rx.var
    def filtered_token_cards(self) -> list[dict[str, str]]:
        query = self.token_query.strip().lower()
        if not query:
            return self.token_cards
        matched = []
        for card in self.token_cards:
            blob = " ".join(
                str(card.get(field) or "")
                for field in ("tpp", "tpp_id", "user", "user_id", "scope", "access", "created")
            ).lower()
            if query in blob:
                matched.append(card)
        return matched

    @rx.event
    def open_token_detail(self, index: str):
        try:
            selected = int(index)
        except (TypeError, ValueError):
            return
        if selected < 0 or selected >= len(self.token_payloads):
            return
        card = next((item for item in self.token_cards if item.get("index") == str(selected)), {})
        details = describe_token(self.token_payloads[selected])
        self.token_detail_index = str(selected)
        self.token_detail_tpp = card.get("tpp", "")
        self.token_detail_user = card.get("user", "")
        self.token_detail_user_id = card.get("user_id", "")
        self.token_detail_scope = card.get("scope", "")
        self.token_detail_access = card.get("access", "")
        self.token_detail_created = card.get("created", "")
        self.token_detail_refresh_created = card.get("refresh_created", "")
        self.token_detail_expires = details["expires"]
        self.token_access = details["access"]
        self.token_refresh = details["refresh"]
        self.token_meta = details["meta"]
        self.token_parsed = details["parsed"]
        self.token_json = details["json"]
        self.token_client_id = details["client_id"]
        self.introspect_summary = ""
        self.introspect_json = ""
        self.token_detail_open = True

    @rx.event
    def close_token_detail(self):
        self.token_detail_open = False
        self.token_revoke_open = False

    @rx.event
    def set_token_action_type(self, value: str | list[str]):
        mode = value[0] if isinstance(value, list) else value
        if mode in {"Access", "Refresh"}:
            self.token_action_type = mode

    def _open_token_credentials(self, token_type: str) -> tuple[str, str]:
        try:
            selected = int(self.token_detail_index)
        except (TypeError, ValueError):
            return "", ""
        if selected < 0 or selected >= len(self.token_payloads):
            return "", ""
        details = describe_token(self.token_payloads[selected])
        value = details["access"] if token_type == "Access Token" else details["refresh"]
        return details["client_id"], value

    @rx.event
    def open_token_revoke(self):
        if self.token_detail_index == "":
            self._notify("Select a token first.", "warning")
            return
        self.token_revoke_open = True

    @rx.event
    def show_token(self, label: str):
        self.token_label = label
        if label not in self.token_labels:
            return
        details = describe_token(self.token_payloads[self.token_labels.index(label)])
        self.token_access = details["access"]
        self.token_refresh = details["refresh"]
        self.token_meta = details["meta"]
        self.token_parsed = details["parsed"]
        self.token_json = details["json"]
        self.token_client_id = details["client_id"]

    def _token_value(self, label: str, token_type: str) -> tuple[str, str]:
        if label not in self.token_labels:
            return "", ""
        details = describe_token(self.token_payloads[self.token_labels.index(label)])
        value = details["access"] if token_type == "Access Token" else details["refresh"]
        return details["client_id"], value

    @rx.event(background=True)
    async def introspect_selected(self):
        async with self:
            token_type = "Access Token" if self.token_action_type == "Access" else "Refresh Token"
            client_id, token_value = self._open_token_credentials(token_type)
            if not client_id:
                self._notify("Select a token that has client credentials.", "error")
                return
            self.busy = True
            self.busy_message = "Introspecting token..."
        result = await asyncio.to_thread(run_introspection, token_value, client_id)
        async with self:
            self.busy = False
            self.introspect_summary = result["summary"] or result["message"]
            self.introspect_json = result["json"]
            self._notify(result["message"], "success" if result["ok"] else "error")

    @rx.event(background=True)
    async def revoke_selected(self):
        async with self:
            token_type = "Access Token" if self.token_action_type == "Access" else "Refresh Token"
            client_id, token_value = self._open_token_credentials(token_type)
            if not client_id:
                self.token_revoke_open = False
                self._notify("Select a token that has client credentials.", "error")
                return
            self.token_revoke_open = False
            self.busy = True
            self.busy_message = "Revoking token..."
        result = await asyncio.to_thread(run_revocation, token_value, client_id, token_type)
        async with self:
            self.busy = False
            self._notify(result["message"], "success" if result["ok"] else "error")

    @rx.event
    def open_consents(self):
        self.refresh_sidebar_options()
        self.form_owner_id = self.selected_user_id
        self.form_oauth_client_id = self.selected_client_id
        self.form_disponent_ids = self.selected_user_id
        self.form_delete_user_id = self.selected_user_id
        self.form_delete_client_id = self.selected_client_id
        if not self.selected_client_id and not self.selected_user_id:
            self._clear_consents("missing_context")
            return
        return AppState.load_consents

    def _clear_consents(self, status: str = ""):
        self.consent_rows = []
        self.consent_labels = []
        self.consent_payloads = []
        self.consent_cards = []
        self.consent_filter_info = ""
        self.consent_empty_message = ""
        self.consent_count_label = ""
        self.consent_status = status
        self.consent_status_text = ""
        self.consent_detail_open = False

    def _fail_consents(self, error: str):
        self._clear_consents("unavailable" if is_service_unavailable(error or "") else "error")
        self.consent_status_text = "Service unavailable" if self.consent_status == "unavailable" else (error or "Failed to fetch consents.")

    def _apply_consents(self, consents: list):
        data = consents_view(consents, self.selected_client_id, self.selected_user_id)
        self.consent_count_label = data["count"]
        self.consent_filter_info = data["filter_info"]
        self.consent_empty_message = data["empty_message"]
        self.consent_rows = data["rows"]
        self.consent_labels = data["labels"]
        self.consent_payloads = data["payloads"]
        self.consent_cards = data["cards"]
        self.consent_status = "ready"
        self.consent_status_text = ""
        self.consent_detail_open = False
        self.consent_label = ""
        self.consent_summary = ""
        self.consent_meta = ""
        self.consent_json = ""

    @rx.event(background=True)
    async def load_consents(self):
        async with self:
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            if not client_id and not user_id:
                self._clear_consents("missing_context")
                return
            self.busy = True
            self.busy_message = "Fetching consents..."
            self.consent_detail_open = False
            self.consent_cards = []
        consents, error = await asyncio.to_thread(fetch_consents, client_id, user_id)
        async with self:
            self.busy = False
            if consents is None:
                self._fail_consents(error)
                return
            self._apply_consents(consents)

    @rx.var
    def filtered_consent_cards(self) -> list[dict[str, str]]:
        query = self.consent_query.strip().lower()
        if not query:
            return self.consent_cards
        matched = []
        for card in self.consent_cards:
            blob = " ".join(
                str(card.get(field) or "")
                for field in ("owner", "owner_id", "tpp", "tpp_id", "scopes", "id", "valid_to")
            ).lower()
            if query in blob:
                matched.append(card)
        return matched

    @rx.event
    def open_consent_detail(self, index: str):
        try:
            selected = int(index)
        except (TypeError, ValueError):
            return
        if selected < 0 or selected >= len(self.consent_payloads):
            return
        details = describe_consent(self.consent_payloads[selected])
        self.consent_detail_id = details["id"]
        self.consent_detail_owner = details["owner"]
        self.consent_detail_owner_id = details["owner_id"]
        self.consent_detail_client = details["client"]
        self.consent_detail_client_id = details["client_id"]
        self.consent_detail_scopes = details["scopes"]
        self.consent_detail_disponents = details["disponents"]
        self.consent_detail_valid_from = details["valid_from"]
        self.consent_detail_valid_to = details["valid_to"]
        self.consent_detail_recalled = details["recalled"]
        self.consent_summary = details["summary"]
        self.consent_meta = details["meta"]
        self.consent_json = details["json"]
        self.consent_detail_open = True

    @rx.event
    def close_consent_detail(self):
        self.consent_detail_open = False

    @rx.event
    def show_consent(self, label: str):
        self.consent_label = label
        if label not in self.consent_labels:
            return
        details = describe_consent(self.consent_payloads[self.consent_labels.index(label)])
        self.consent_summary = details["summary"]
        self.consent_meta = details["meta"]
        self.consent_json = details["json"]

    @rx.event(background=True)
    async def submit_consent(self):
        async with self:
            self.busy = True
            self.busy_message = "Creating consent..."
            scopes = []
            if self.scope_balance:
                scopes.append("AISP.Balance")
            if self.scope_account_list:
                scopes.append("AISP.AccountList")
            if self.scope_transactions:
                scopes.append("AISP.TransactionList")
            if self.scope_payment:
                scopes.append("PISP.PaymentInitiation")
            args = (
                self.form_owner_id,
                self.form_oauth_client_id,
                self.form_oauth_client_name,
                self.form_disponent_ids,
                scopes,
            )
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        result = await asyncio.to_thread(create_consent, *args)
        consents = None
        if result["ok"] and user_id:
            consents, _error = await asyncio.to_thread(fetch_consents, client_id, user_id)
        async with self:
            self.busy = False
            self.consent_output = result["output"]
            self._notify(result["message"], "success" if result["ok"] else "error")
            if consents is not None:
                self._apply_consents(consents)

    @rx.event(background=True)
    async def submit_delete_consents(self):
        async with self:
            self.busy = True
            self.busy_message = "Deleting consents..."
            args = (
                self.selected_client_id,
                self.selected_user_id,
                self.form_delete_user_id,
                self.form_delete_client_id,
            )
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        result = await asyncio.to_thread(delete_consents, *args)
        consents = None
        if result["ok"] and user_id:
            consents, _error = await asyncio.to_thread(fetch_consents, client_id, user_id)
        async with self:
            self.busy = False
            self.consent_output = result["output"]
            self._notify(result["message"], "success" if result["ok"] else "error")
            if consents is not None:
                self._apply_consents(consents)

    @rx.event(background=True)
    async def submit_delete_consent_by_id(self):
        async with self:
            self.busy = True
            self.busy_message = "Deleting consent..."
            consent_id = self.form_delete_consent_id
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        result = await asyncio.to_thread(delete_consent_by_id, consent_id)
        consents = None
        if result["ok"] and user_id:
            consents, _error = await asyncio.to_thread(fetch_consents, client_id, user_id)
        async with self:
            self.busy = False
            self.consent_output = result["output"]
            self._notify(result["message"], "success" if result["ok"] else "error")
            if consents is not None:
                self._apply_consents(consents)

    def _apply_account_view(self, data: dict):
        self.account_logs = [*self.account_logs, *data["logs"]][-80:]
        self.account_status = data["status"]
        self.account_status_text = data["status_text"]
        self.account_rows = data["rows"]
        self.account_labels = data["labels"]
        self.account_payloads = data["payloads"]
        self.account_cards = data["cards"]
        self.account_carousel_index = len(self.account_cards) // 2
        if not self.notice and data["status"] == "ready" and data["status_text"]:
            self.notice = data["status_text"]
            self.notice_level = "info"
            self.notice_token += 1
        self.account_detail_open = False
        self.account_json = data["json"]
        self.account_output = data["output"]
        self.refresh_error = data["refresh_error"]
        if self.account_labels:
            if self.tx_account_label not in self.account_labels:
                self.tx_account_label = self.account_labels[0]
            if self.pay_account_label not in self.account_labels:
                self.select_payment_account(self.account_labels[0])
        table = payment_table()
        self.payment_labels = table["labels"]
        self.payment_rows = table["rows"]
        if self.payment_labels and self.payment_label not in self.payment_labels:
            self.payment_label = self.payment_labels[0]
        if not self.pay_instruction_id:
            self.pay_instruction_id = f"NejakeID{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _select_carousel_index(self, index: int):
        if not self.account_cards:
            self.account_carousel_index = 0
            return
        self.account_carousel_index = max(0, min(index, len(self.account_cards) - 1))

    @rx.event
    def show_account_card(self, index: str):
        try:
            self._select_carousel_index(int(index))
        except (TypeError, ValueError):
            return

    @rx.event
    def carousel_prev(self):
        self._select_carousel_index(self.account_carousel_index - 1)

    @rx.event
    def carousel_next(self):
        self._select_carousel_index(self.account_carousel_index + 1)

    @rx.event
    def open_account_detail(self, index: str):
        try:
            selected = int(index)
        except (TypeError, ValueError):
            return
        if selected < 0 or selected >= len(self.account_cards):
            return
        card = self.account_cards[selected]
        payload = self.account_payloads[selected] if selected < len(self.account_payloads) else ""
        details = account_detail_fields(payload)
        self.account_carousel_index = selected
        self.account_detail_name = details["name"] or card.get("name") or ""
        self.account_detail_product = details["product"]
        self.account_detail_iban = details["iban"] or card.get("iban") or ""
        self.account_detail_number = details["number"]
        self.account_detail_currency = details["currency"] or card.get("currency") or ""
        self.account_detail_id = details["id"] or card.get("id") or ""
        self.account_detail_bank = details["bank"]
        self.account_detail_bic = details["bic"]
        self.account_detail_country = details["country"]
        self.account_detail_owner = details["owner"]
        self.account_detail_gradient = card.get("gradient") or ""
        self.account_balances = []
        self.account_balance_note = "Loading balances..."
        self.account_detail_open = True
        self.tx_rows = []
        self.tx_records = []
        self.tx_page_index = 0
        self.tx_total = -1
        self.tx_selected_index = ""
        self.tx_detail_open = False
        self.tx_fullscreen = False
        self.tx_json = ""
        self.tx_output = ""
        self.pay_detail_open = False
        self.pay_page_index = 0
        if selected < len(self.account_labels):
            label = self.account_labels[selected]
            self.tx_account_label = label
            self.select_payment_account(label)
        self._apply_creditor_choices()
        self.pay_date = datetime.now().strftime("%Y-%m-%d")
        self.pay_instruction_id = f"NejakeID{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._refresh_payment_table()
        self._refresh_account_payments()
        return [AppState.fetch_account_balance, AppState.fetch_account_transactions]

    @rx.event
    def close_account_detail(self):
        self.account_detail_open = False

    @rx.event
    def refresh_accounts_view(self):
        if self.account_detail_open:
            self._refresh_account_payments()
            return [AppState.fetch_account_balance, AppState.refresh_account_transactions]
        return AppState.load_accounts

    @rx.event
    def open_accounts(self):
        self.refresh_sidebar_options()
        self._apply_account_list_mode()
        if not self.selected_client_id or not self.selected_user_id:
            self.account_status = "missing_context"
            self.account_rows = []
            self.account_labels = []
            self.account_cards = []
            self.account_detail_open = False
            self._notify("Select both Application and User in the sidebar.", "warning")
            return
        return AppState.load_accounts

    @rx.event(background=True)
    async def load_accounts(self):
        async with self:
            if not self.selected_client_id or not self.selected_user_id:
                self.account_status = "missing_context"
                self._notify("Select both Application and User in the sidebar.", "warning")
                return
            if self.notice == "Select both Application and User in the sidebar.":
                self.notice = ""
            self.busy = True
            self.busy_message = "Loading accounts..."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        data = await prepare_accounts(client_id, user_id)
        async with self:
            self.busy = False
            self._apply_account_view(data)

    @rx.var
    def filtered_account_cards(self) -> list[dict[str, str]]:
        query = self.account_table_query.strip().lower()
        if not query:
            return self.account_cards
        fields = ("id", "number", "iban", "name", "currency")
        folded = query.replace(" ", "")
        matched = []
        for card in self.account_cards:
            for field in fields:
                raw = str(card.get(field) or "").lower()
                if query in raw or folded in raw.replace(" ", ""):
                    matched.append(card)
                    break
        return matched

    @rx.event
    def set_account_list_mode(self, value: str | list[str]):
        mode = value[0] if isinstance(value, list) else value
        if mode in {"carousel", "table"}:
            self.account_list_mode = mode

    @rx.event
    def save_loaded_accounts(self):
        if self.account_detail_open:
            index = self.account_carousel_index
            if index < 0 or index >= len(self.account_payloads) or not self.account_payloads[index]:
                return self._notify("No account is open.", "warning")
            payloads = [self.account_payloads[index]]
        else:
            if not self.account_payloads:
                return self._notify("No accounts loaded.", "warning")
            payloads = self.account_payloads
        result = save_missing_user_accounts(
            self.selected_user_id,
            self.selected_user_name,
            payloads,
        )
        added = result["added"]
        if self.account_detail_open:
            if added:
                return self._notify("Saved the current account.", "success")
            return self._notify("The current account is already saved.", "info")
        if added:
            return self._notify(f"Saved {added} account(s).", "success")
        return self._notify("Loaded accounts are already saved.", "info")

    @rx.event(background=True)
    async def authorize(self):
        async with self:
            if not self.selected_client_id or not self.selected_user_id:
                self._notify("Select both Application and User first.", "warning")
                return
            self.busy = True
            self.busy_message = "Authorization is running. Complete it in the browser window."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            self.account_logs = [
                *self.account_logs,
                {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "level": "info",
                    "message": "Starting authorization flow. A browser window will open.",
                    "color": "blue",
                },
            ]
        result = await asyncio.to_thread(authorize_and_exchange, client_id, user_id)
        data = await prepare_accounts(client_id, user_id)
        async with self:
            self.busy = False
            self._notify(result["message"], "success" if result["ok"] else "warning")
            self._apply_account_view(data)

    @rx.event
    def clear_account_logs(self):
        self.account_logs = []
        self.refresh_error = ""

    @rx.event
    def show_tx_detail(self, index: str):
        if not index:
            return
        self.tx_selected_index = index
        self.tx_detail_open = True

    @rx.event
    def show_payment_detail(self, index: str):
        if not index:
            return
        self.pay_selected_index = index
        self.pay_action_output = ""
        self.pay_detail_open = True

    @rx.event
    def open_tx_fullscreen(self):
        self.tx_fullscreen = True

    @rx.event
    def open_pay_form(self):
        self.pay_edit_index = ""
        self._apply_creditor_choices()
        self.pay_form_open = True

    def _apply_creditor_choices(self):
        debtor = self.pay_debtor_iban or self.account_detail_iban
        choices = creditor_account_choices(debtor)
        wanted = str(self.pay_creditor_iban or "").replace(" ", "").upper()
        selected = next(
            (item for item in choices if item["iban"].replace(" ", "").upper() == wanted),
            None,
        )
        if selected is None and self.pay_edit_index and wanted:
            selected = {
                "label": self.pay_creditor_iban,
                "iban": self.pay_creditor_iban,
                "currency": self.pay_creditor_currency or "",
            }
            choices = [selected, *choices]
        elif selected is None and choices:
            selected = choices[0]
        self.pay_creditor_options = [item["label"] for item in choices]
        if selected:
            self.pay_creditor_label = selected["label"]
            self.pay_creditor_iban = selected["iban"]
            if selected["currency"]:
                self.pay_creditor_currency = selected["currency"]
            return
        self.pay_creditor_label = ""
        self.pay_creditor_iban = ""

    def _fill_payment_form(self, payment: dict):
        body = payment.get("requestBody") if isinstance(payment.get("requestBody"), dict) else {}
        instructed = ((body.get("amount") or {}).get("instructedAmount") or {})
        amount_value = str(instructed.get("value") or "").strip()
        currency = str(instructed.get("currency") or "").strip()
        amount_text = str(payment.get("amount + currency") or "").strip()
        if not amount_value and amount_text:
            parts = amount_text.split()
            amount_value = parts[0] if parts else ""
            currency = currency or (parts[1] if len(parts) > 1 else "")
        creditor = body.get("creditorAccount") if isinstance(body.get("creditorAccount"), dict) else {}
        creditor_id = creditor.get("identification") if isinstance(creditor.get("identification"), dict) else {}
        creditor_iban = str(creditor_id.get("iban") or payment.get("creditorIban") or "")
        creditor_currency = str(creditor.get("currency") or "")
        references = (
            ((body.get("remittanceInformation") or {}).get("structured") or {}).get("creditorReferenceInformation") or {}
        ).get("reference") or []
        symbols = {"VS": "", "SS": "", "KS": ""}
        if isinstance(references, list):
            for item in references:
                text = str(item)
                if ":" in text:
                    key, value = text.split(":", 1)
                    if key in symbols:
                        symbols[key] = value
        notes = body.get("x-paymentNotes") if isinstance(body.get("x-paymentNotes"), dict) else {}
        unstructured = (body.get("remittanceInformation") or {}).get("unstructured")
        priority = (
            (body.get("paymentTypeInformation") or {}).get("instructionPriority")
            or payment.get("instructionPriority")
            or "NORM"
        )
        identification = (
            (body.get("paymentIdentification") or {}).get("instructionIdentification")
            or payment.get("instructionIdentification")
            or ""
        )
        self.pay_instruction_id = str(identification)
        self.pay_amount = amount_value
        if currency:
            self.pay_currency = currency
        self.pay_date = str(body.get("requestedExecutionDate") or payment.get("requestedExecutionDate") or "")
        self.pay_creditor_iban = creditor_iban
        if creditor_currency:
            self.pay_creditor_currency = creditor_currency
        self.pay_vs = symbols["VS"]
        self.pay_ss = symbols["SS"]
        self.pay_ks = symbols["KS"]
        self.pay_unstructured = "" if unstructured is None else str(unstructured)
        self.pay_priority = str(priority or "NORM")
        self.pay_note_requestor = str(notes.get("noteForRequestor") or "")
        self.pay_note_bank = str(notes.get("noteForBank") or "")
        self.pay_narrative = str(notes.get("narrative") or "")

    @rx.event
    def open_payment_row(self, index: str):
        if not index:
            return
        try:
            selected = int(index)
        except (TypeError, ValueError):
            return
        payments = load_created_payments()
        if selected < 0 or selected >= len(payments):
            return
        payment = payments[selected]
        if str(payment.get("status") or "").strip().upper() == "DRAFT":
            self._fill_payment_form(payment)
            self.pay_edit_index = index
            self._apply_creditor_choices()
            self.pay_form_open = True
            self.pay_detail_open = False
            return
        self.pay_selected_index = index
        self.pay_action_output = ""
        self.pay_detail_open = True

    @rx.event
    def delete_draft_payment(self):
        if not str(self.pay_edit_index).isdigit():
            return self._notify("Select a draft payment first.", "warning")
        if not delete_local_payment(int(self.pay_edit_index)):
            return self._notify("The draft could not be deleted.", "error")
        table = payment_table()
        self.payment_labels = table["labels"]
        self.payment_rows = table["rows"]
        if self.payment_labels and self.payment_label not in self.payment_labels:
            self.payment_label = self.payment_labels[0]
        elif not self.payment_labels:
            self.payment_label = ""
        self._refresh_account_payments()
        self.pay_form_open = False
        self.pay_edit_index = ""
        return self._notify("Draft payment deleted.", "success")

    @rx.event
    def select_creditor_account(self, label: str):
        self.pay_creditor_label = label
        debtor = self.pay_debtor_iban or self.account_detail_iban
        for item in creditor_account_choices(debtor):
            if item["label"] == label:
                self.pay_creditor_iban = item["iban"]
                if item["currency"]:
                    self.pay_creditor_currency = item["currency"]
                return
        if "·" not in str(label):
            self.pay_creditor_iban = label

    @rx.event
    def tx_page_prev(self):
        if self.tx_page_index <= 0:
            return
        return AppState.fetch_account_transactions(self.tx_page_index - 1)

    @rx.event
    def tx_page_next(self):
        return AppState.fetch_account_transactions(self.tx_page_index + 1)

    @rx.event
    def refresh_account_transactions(self):
        return AppState.fetch_account_transactions(self.tx_page_index)

    @rx.event
    def pay_page_prev(self):
        if self.pay_page_index > 0:
            self.pay_page_index -= 1

    @rx.event
    def pay_page_next(self):
        if (self.pay_page_index + 1) * TX_PAGE_SIZE < len(self.account_payment_records):
            self.pay_page_index += 1

    @rx.event(background=True)
    async def fetch_account_transactions(self, page: int = 0):
        async with self:
            if self.tx_account_label not in self.account_labels:
                return self._notify("Select an account first.", "warning")
            payload = self.account_payloads[self.account_labels.index(self.tx_account_label)]
            selected_id = account_id(payload)
            if not selected_id:
                return self._notify("Selected account has no id.", "error")
            page = max(0, int(page))
            self.busy = True
            self.busy_message = "Fetching transactions..."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        result = await asyncio.to_thread(
            fetch_transactions, client_id, user_id, selected_id, page, TX_PAGE_SIZE,
        )
        async with self:
            self.busy = False
            if not result["success"]:
                self.tx_output = "\n".join(part for part in (result["output"], result["error"]) if part)
                return self._notify("Failed to fetch transactions.", "error")
            parsed = extract_json(result["output"])
            if not parsed:
                self.tx_output = result["output"]
                return self._notify("Could not parse the transactions response.", "warning")
            records = transaction_records(parsed)
            self.tx_page_index = page
            self.tx_total = transaction_total(parsed)
            self.tx_records = records
            self.tx_rows = transaction_rows(parsed)
            self.tx_json = pretty(parsed)
            self.tx_output = ""
            if self.tx_total >= 0:
                found = self.tx_total
            else:
                found = page * TX_PAGE_SIZE + len(records)
            return self._notify(f"Found {found} transaction(s).", "success")

    @rx.event(background=True)
    async def fetch_account_balance(self):
        async with self:
            account_id = self.account_detail_id
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            if not account_id or not client_id or not user_id:
                self.account_balances = []
                self.account_balance_note = "Select an account with an active context."
                return
        result = await asyncio.to_thread(fetch_balance, client_id, user_id, account_id)
        async with self:
            if self.account_detail_id != account_id:
                return
            if not result["success"]:
                self.account_balances = []
                self.account_balance_note = "Could not load balances."
                self._log("Could not load balances.", "error")
                return
            parsed = extract_json(result["output"])
            if not parsed:
                self.account_balances = []
                self.account_balance_note = "Could not read the balance response."
                self._log("Could not read the balance response.", "warning")
                return
            self.account_balances = balance_entries(parsed)
            self.account_balance_note = "" if self.account_balances else "No balances returned."
            self._log(
                f"Loaded {len(self.account_balances)} balance(s) for account {account_id}.",
                "info",
            )

    def _refresh_account_payments(self):
        self.account_payment_records = account_payment_records(
            self.account_detail_id,
            self.account_detail_iban,
        )
        pages = max(1, (len(self.account_payment_records) + TX_PAGE_SIZE - 1) // TX_PAGE_SIZE)
        if self.pay_page_index >= pages:
            self.pay_page_index = pages - 1

    def _refresh_payment_table(self):
        table = payment_table()
        self.payment_labels = table["labels"]
        self.payment_rows = table["rows"]
        if self.payment_labels and self.payment_label not in self.payment_labels:
            self.payment_label = self.payment_labels[0]

    @rx.event
    def refresh_payments(self):
        self._refresh_payment_table()
        self._refresh_account_payments()

    @rx.event
    def select_payment_account(self, label: str):
        self.pay_account_label = label
        if label not in self.account_labels:
            return
        payload = self.account_payloads[self.account_labels.index(label)]
        self.pay_currency = account_currency(payload)
        iban = account_iban(payload)
        if iban:
            self.pay_debtor_iban = iban

    def _payment_body(self) -> dict:
        return build_payment_body(
            self.pay_instruction_id,
            self.pay_amount or "0",
            self.pay_currency,
            self.pay_date,
            self.pay_debtor_iban,
            self.pay_creditor_iban,
            self.pay_creditor_currency,
            self.pay_unstructured,
            self.pay_vs,
            self.pay_ss,
            self.pay_ks,
            self.pay_note_requestor,
            self.pay_note_bank,
            self.pay_narrative,
            self.pay_priority or "NORM",
        )

    @rx.event
    def preview_payment(self):
        try:
            self.pay_request_json = pretty(self._payment_body())
        except Exception as exc:
            self._notify(f"Could not build the payment body: {exc}", "error")

    @rx.event(background=True)
    async def submit_payment(self):
        async with self:
            try:
                body = self._payment_body()
            except Exception as exc:
                self._notify(f"Could not build the payment body: {exc}", "error")
                return
            self.pay_request_json = pretty(body)
            self.busy = True
            self.busy_message = "Creating payment..."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
            account_id = self.account_detail_id
            edit_index = self.pay_edit_index
        result = await asyncio.to_thread(create_payment, client_id, user_id, body)
        async with self:
            self.busy = False
            output = "\n".join(part for part in (result["output"], result["error"]) if part)
            status_code = response_http_status(result["output"])
            parsed = extract_json(result["output"])
            if not isinstance(parsed, dict):
                parsed = {}
            accepted = status_code == 200
            if accepted and not parsed:
                self.pay_output = output
                return self._notify("Payment request finished, but the response was not JSON.", "warning")
            replace_index = int(edit_index) if str(edit_index).isdigit() else None
            saved = save_created_payment(
                body,
                parsed,
                account_id,
                user_id,
                replace_index=replace_index,
                status_override="" if accepted else "DRAFT",
            )
            if not saved:
                self.pay_output = output
                if accepted:
                    return self._notify("Payment was created, but it could not be saved locally.", "warning")
                return self._notify("Payment was not accepted and could not be saved as a draft.", "error")
            table = payment_table()
            self.payment_labels = table["labels"]
            self.payment_rows = table["rows"]
            if self.payment_labels:
                label_index = replace_index if replace_index is not None else -1
                self.payment_label = self.payment_labels[label_index]
            self._refresh_account_payments()
            if not accepted:
                self.pay_form_open = False
                self.pay_edit_index = ""
                self.pay_output = output
                status_text = str(status_code) if status_code is not None else "no HTTP 200"
                return self._notify(f"Payment was not accepted ({status_text}) and was saved as a draft.", "warning")
            payments = load_created_payments()
            saved_index = replace_index if replace_index is not None else len(payments) - 1
            payment_id = ""
            if 0 <= saved_index < len(payments):
                payment_id = str(payments[saved_index].get("transactionIdentification") or "")
            self.pay_response_json = pretty(parsed)
            self.pay_output = ""
            if not payment_id:
                self.pay_form_open = False
                self.pay_edit_index = ""
                return self._notify("Payment created and saved.", "success")
            self.busy = True
            self.busy_message = "Checking payment status..."
        status_result = await asyncio.to_thread(run_payment_action, client_id, user_id, "status", saved_index)
        async with self:
            self.busy = False
            self.payment_labels = status_result["table"]["labels"]
            self.payment_rows = status_result["table"]["rows"]
            if self.payment_labels:
                self.payment_label = self.payment_labels[saved_index if saved_index < len(self.payment_labels) else -1]
            self._refresh_account_payments()
            self.pay_form_open = False
            self.pay_edit_index = ""
            if status_result["ok"]:
                return self._notify("Payment created and status updated.", "success")
            return self._notify("Payment created, but the status could not be updated.", "warning")

    @rx.event(background=True)
    async def payment_action(self, action: str):
        async with self:
            if self.payment_label not in self.payment_labels:
                return self._notify("Select a payment first.", "warning")
            index = self.payment_labels.index(self.payment_label)
            self.busy = True
            self.busy_message = f"Running payment {action}..."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        result = await asyncio.to_thread(run_payment_action, client_id, user_id, action, index)
        async with self:
            self.busy = False
            self.payment_action_output = result["output"]
            self.payment_labels = result["table"]["labels"]
            self.payment_rows = result["table"]["rows"]
            if self.payment_labels and self.payment_label not in self.payment_labels:
                self.payment_label = self.payment_labels[0]
            self._refresh_account_payments()
            return self._notify(result["message"], "success" if result["ok"] else "error")

    @rx.event(background=True)
    async def run_selected_payment_action(self, action: str):
        async with self:
            if not self.pay_selected_index:
                return self._notify("Select a payment first.", "warning")
            try:
                index = int(self.pay_selected_index)
            except ValueError:
                return self._notify("Select a payment first.", "warning")
            self.busy = True
            self.busy_message = f"Running payment {action}..."
            client_id = self.selected_client_id
            user_id = self.selected_user_id
        result = await asyncio.to_thread(run_payment_action, client_id, user_id, action, index)
        async with self:
            self.busy = False
            self.pay_action_output = result.get("output") or ""
            self._refresh_payment_table()
            self._refresh_account_payments()
            level = "success" if result.get("ok") else "error"
            return self._notify(result.get("message") or "Payment action finished.", level)


_parent_vars = set(rx.State.base_vars)
for _field_name, _field_var in AppState.base_vars.items():
    if _field_name in _parent_vars or f"set_{_field_name}" in AppState.__dict__:
        continue
    AppState._create_setter(_field_name, _field_var)
