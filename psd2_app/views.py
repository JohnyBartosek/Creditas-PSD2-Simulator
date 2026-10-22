"""Reflex pages for the PSD2 simulator."""

import reflex as rx

from psd2_app.logic import (
    PRIORITY_OPTIONS,
    SCOPE_OPTIONS,
)
from psd2_app.state import AppState
from psd2_app.ui import (
    copy_block,
    context_picker,
    field,
    json_block,
    log_panel,
    notice_toasts,
    page_shell,
    pre_block,
    sidebar,
)


def _dash_widget(title: str, count) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(title, size="2", weight="medium", color="#667085"),
            rx.text(count, size="7", weight="bold", color="#1c2430", line_height="1"),
            spacing="2",
            align="center",
            width="100%",
        ),
        width="100%",
        padding="1.15rem 1.1rem",
        background="white",
        border="1px solid #e7eaf0",
        border_radius="16px",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def dashboard_page() -> rx.Component:
    return page_shell(
        "Dashboard",
        rx.box(
            rx.grid(
                _dash_widget("TPP Registrations", AppState.dashboard_registration_count),
                _dash_widget("Users", AppState.dashboard_user_count),
                _dash_widget("Mapped Accounts", AppState.dashboard_account_count),
                _dash_widget("Registered Payments", AppState.dashboard_payment_count),
                columns="2",
                spacing="3",
                width="min(32rem, 100%)",
            ),
            width="100%",
            flex="1",
            min_height="0",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        fill=True,
    )


def _user_table_head(label: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.text(label, size="1", weight="medium", color="#667085", style={"letterSpacing": "0.04em"}),
        padding_y="0.75rem",
        padding_x="1rem",
        style={"background": "#f8fafc"},
    )


def _user_row(card) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(card["name"], size="2", weight="medium", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(
                rx.cond(card["id"] != "", card["id"], "—"),
                size="2",
                color="#1c2430",
                style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"},
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["birth"] != "", card["birth"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(
                rx.cond(card["username"] != "", card["username"], "—"),
                size="2",
                color="#1c2430",
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["phone"] != "", card["phone"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        on_click=AppState.open_user_detail(card["index"]),
        cursor="pointer",
        style={"borderBottom": "1px solid #f2f4f7"},
        _hover={"background": "#f4f6ff"},
    )


def _user_list() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon("search", size=16, color="#98a2b3", position="absolute", left="0.9rem", top="0.85rem"),
                rx.input(
                    placeholder="Search name, ID, birth date, username or phone",
                    value=AppState.user_query,
                    on_change=AppState.set_user_query,
                    width="100%",
                    size="3",
                    variant="surface",
                    radius="large",
                    color_scheme="indigo",
                    style={
                        "height": "2.7rem",
                        "paddingLeft": "2.4rem",
                        "background": "white",
                        "border": "1px solid #e4e7ec",
                        "boxShadow": "0 8px 24px rgba(16, 24, 40, 0.05)",
                        "color": "#1c2430",
                    },
                ),
                position="relative",
                width="100%",
            ),
            rx.cond(
                AppState.filtered_user_cards.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                _user_table_head("Name"),
                                _user_table_head("ID"),
                                _user_table_head("Birth date"),
                                _user_table_head("Username"),
                                _user_table_head("Phone"),
                            ),
                        ),
                        rx.table.body(rx.foreach(AppState.filtered_user_cards, _user_row)),
                        width="100%",
                        style={"borderCollapse": "separate", "borderSpacing": "0"},
                    ),
                    width="100%",
                    max_height="min(62vh, 36rem)",
                    overflow_y="auto",
                    background="white",
                    border="1px solid #e7eaf0",
                    border_radius="20px",
                    box_shadow="0 18px 50px rgba(16, 24, 40, 0.08)",
                ),
                rx.callout(
                    rx.cond(AppState.user_cards.length() > 0, "No users match the search.", "No users found."),
                    color_scheme="gray",
                    width="100%",
                ),
            ),
            spacing="3",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="auto",
    )


def _user_hero() -> rx.Component:
    return rx.box(
        rx.box(
            rx.vstack(
                rx.text("User", size="1", color="rgba(255,255,255,0.75)", weight="medium"),
                rx.heading(AppState.user_detail_name, size="6", color="white"),
                rx.text(
                    rx.cond(AppState.user_detail_party_id != "", AppState.user_detail_party_id, "ID unavailable"),
                    size="4",
                    color="white",
                    weight="medium",
                    style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", "letterSpacing": "0.04em"},
                ),
                spacing="1",
                align="start",
            ),
            width="100%",
            padding="1.35rem 1.5rem",
            background="linear-gradient(135deg, #312e81 0%, #4338ca 58%, #6366f1 100%)",
        ),
        rx.grid(
            _detail_fact("Birth date", AppState.user_detail_birth),
            _detail_fact("Phone", AppState.user_detail_phone),
            _detail_fact("Username", AppState.user_detail_username),
            columns="3",
            spacing="4",
            width="100%",
            padding="1rem 1.5rem 1.15rem",
        ),
        width="100%",
        border="1px solid #e4e7ec",
        border_radius="18px",
        overflow="hidden",
        background="white",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _user_detail() -> rx.Component:
    return rx.box(
        rx.vstack(
            _user_hero(),
            rx.grid(
                _copy_widget("Party ID", AppState.user_detail_party_id),
                _copy_widget("Username", AppState.user_detail_username),
                _copy_widget("Password", AppState.user_detail_password),
                _copy_widget("Phone", AppState.user_detail_phone),
                rx.cond(
                    AppState.user_detail_mpin != "",
                    _copy_widget("mPIN", AppState.user_detail_mpin),
                ),
                columns="2",
                spacing="3",
                width="100%",
            ),
            rx.cond(
                AppState.user_auth_code != "",
                rx.vstack(
                    _copy_widget("Authorization code", AppState.user_auth_code),
                    rx.hstack(
                        rx.text(AppState.user_auth_code_status, size="2", color="#667085"),
                        rx.spacer(),
                        rx.button(
                            "Get Token",
                            size="2",
                            radius="large",
                            variant="soft",
                            color_scheme="indigo",
                            on_click=AppState.exchange_open_user_code,
                        ),
                        width="100%",
                        align="center",
                    ),
                    spacing="3",
                    width="100%",
                    align="start",
                ),
            ),
            spacing="4",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        overflow_y="auto",
        display="flex",
        justify_content="center",
        padding_bottom="0.5rem",
    )


def _user_form_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.vstack(
                    rx.dialog.title(rx.cond(AppState.user_edit_mode, "Edit user", "Add user")),
                    rx.text("Party ID, name, birth date, username and password are required.", size="2", color="#667085"),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.dialog.close(
                    rx.icon_button(rx.icon("x", size=16), size="2", variant="ghost", color_scheme="gray", radius="full"),
                ),
                width="100%",
                align="start",
            ),
            rx.vstack(
                rx.grid(
                    _pay_field("Party ID", AppState.form_party_id, AppState.set_form_party_id),
                    _pay_field("Name", AppState.form_name, AppState.set_form_name),
                    _pay_field("Birth date", AppState.form_birth_date, AppState.set_form_birth_date, placeholder="DD.MM.YYYY"),
                    _pay_field("Username", AppState.form_username, AppState.set_form_username),
                    _pay_field("Password", AppState.form_password, AppState.set_form_password, type="password"),
                    _pay_field("Phone", AppState.form_phone, AppState.set_form_phone),
                    _pay_field("mPIN", AppState.form_mpin, AppState.set_form_mpin),
                    columns="2",
                    spacing="3",
                    width="100%",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            size="3",
                            radius="large",
                            variant="soft",
                            color_scheme="gray",
                            style={"minWidth": "7rem"},
                        ),
                    ),
                    rx.button(
                        "Save user",
                        size="3",
                        radius="large",
                        on_click=AppState.save_user,
                        style={"minWidth": "9.5rem", "background": "#4f46e5", "color": "white"},
                    ),
                    width="100%",
                    spacing="3",
                    padding_top="0.35rem",
                    justify="end",
                ),
                spacing="3",
                width="100%",
                align="start",
            ),
            max_width="42rem",
            style={
                "borderRadius": "22px",
                "padding": "1.35rem 1.4rem 1.15rem",
                "border": "1px solid #e7eaf0",
                "boxShadow": "0 24px 60px rgba(16, 24, 40, 0.16)",
                "background": "white",
            },
        ),
        open=AppState.user_form_open,
        on_open_change=AppState.set_user_form_open,
    )


def _user_delete_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Delete user"),
            rx.text(
                "This deletes ",
                AppState.user_detail_name,
                " and cannot be undone.",
                size="2",
                color="#667085",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button("Cancel", size="2", radius="large", variant="soft", color_scheme="gray"),
                ),
                rx.button(
                    "Delete",
                    size="2",
                    radius="large",
                    color_scheme="red",
                    on_click=AppState.submit_delete_user,
                ),
                spacing="2",
                justify="end",
                width="100%",
                margin_top="1rem",
            ),
            max_width="28rem",
        ),
        open=AppState.user_delete_open,
        on_open_change=AppState.set_user_delete_open,
    )


def _otp_result_row(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(
                    rx.cond(item["otp"] != "", item["otp"], "—"),
                    size="5",
                    weight="bold",
                    color="#1c2430",
                    style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", "letterSpacing": "0.08em"},
                ),
                rx.text(
                    rx.cond(item["time"] != "", item["time"], "Time unavailable"),
                    size="1",
                    color="#667085",
                ),
                rx.hstack(
                    rx.cond(
                        item["status"] != "",
                        rx.text(item["status"], size="1", color="#4338ca", weight="medium"),
                    ),
                    rx.cond(
                        item["phone"] != "",
                        rx.text(item["phone"], size="1", color="#98a2b3"),
                    ),
                    spacing="2",
                    align="center",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("copy", size=14),
                "Copy",
                size="1",
                variant="soft",
                color_scheme="indigo",
                radius="large",
                disabled=item["otp"] == "",
                on_click=rx.set_clipboard(item["otp"]),
            ),
            width="100%",
            align="center",
            spacing="3",
        ),
        width="100%",
        padding="0.9rem 1rem",
        background="white",
        border="1px solid #e7eaf0",
        border_radius="14px",
    )


def _user_otp_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.vstack(
                    rx.dialog.title("OTP codes"),
                    rx.text(
                        AppState.user_detail_name,
                        " · last 30 minutes",
                        size="2",
                        color="#667085",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.dialog.close(
                    rx.icon_button(rx.icon("x", size=16), size="2", variant="ghost", color_scheme="gray", radius="full"),
                ),
                width="100%",
                align="start",
            ),
            rx.cond(
                AppState.user_otp_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Fetching OTP codes...", size="2", color="#667085"),
                        spacing="3",
                        align="center",
                    ),
                    width="100%",
                    min_height="8rem",
                ),
                rx.cond(
                    AppState.user_otp_error != "",
                    rx.callout(AppState.user_otp_error, color_scheme="red", width="100%"),
                    rx.cond(
                        AppState.user_otp_items.length() > 0,
                        rx.vstack(
                            rx.foreach(AppState.user_otp_items, _otp_result_row),
                            spacing="2",
                            width="100%",
                            max_height="24rem",
                            overflow_y="auto",
                        ),
                        rx.callout("No OTP codes in the last 30 minutes.", color_scheme="gray", width="100%"),
                    ),
                ),
            ),
            max_width="32rem",
            style={
                "borderRadius": "22px",
                "padding": "1.35rem 1.4rem 1.25rem",
                "border": "1px solid #e7eaf0",
                "boxShadow": "0 24px 60px rgba(16, 24, 40, 0.16)",
                "background": "white",
            },
        ),
        open=AppState.user_otp_open,
        on_open_change=AppState.set_user_otp_open,
    )


def _users_header() -> rx.Component:
    return rx.cond(
        AppState.user_detail_open,
        rx.hstack(
            _accounts_icon("arrow-left", AppState.close_user_detail, "Users"),
            rx.button(
                "Log to IB",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="indigo",
                on_click=AppState.login_open_user,
            ),
            rx.button(
                "Authorize",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="indigo",
                on_click=AppState.authorize_open_user,
            ),
            rx.button(
                "Get OTP",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="indigo",
                on_click=AppState.get_user_otps,
            ),
            rx.button(
                "Edit",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="indigo",
                on_click=AppState.open_edit_user,
            ),
            rx.button(
                "Delete",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="red",
                on_click=AppState.open_user_delete,
            ),
            spacing="2",
            align="center",
        ),
        rx.button(
            "Add user",
            size="2",
            radius="large",
            on_click=AppState.open_create_user,
            style={"background": "#4f46e5", "color": "white"},
        ),
    )


def users_page() -> rx.Component:
    return page_shell(
        rx.cond(AppState.user_detail_open, "User detail", "Users"),
        rx.box(
            rx.cond(AppState.user_detail_open, _user_detail(), _user_list()),
            flex="1",
            min_height="0",
            width="100%",
            overflow="hidden",
        ),
        _user_form_dialog(),
        _user_delete_dialog(),
        _user_otp_dialog(),
        header_action=_users_header(),
        fill=True,
    )


def configuration_page() -> rx.Component:
    return page_shell(
        "Configuration",
        rx.box(
            rx.box(
            rx.vstack(
                rx.grid(
                    context_picker(
                        "User",
                        "user-round",
                        "Select user",
                        AppState.form_config_party_name,
                        AppState.form_config_party_id,
                        AppState.config_user_query,
                        AppState.set_config_user_query,
                        AppState.filtered_config_user_options,
                        AppState.form_config_party_label,
                        AppState.pick_config_user,
                        AppState.config_user_picker_open,
                        AppState.set_config_user_picker_open,
                        "Search user",
                    ),
                    context_picker(
                        "TPP",
                        "building-2",
                        "Select TPP",
                        AppState.form_config_client_name,
                        AppState.form_config_client_oauth,
                        AppState.config_client_query,
                        AppState.set_config_client_query,
                        AppState.filtered_config_client_options,
                        AppState.form_config_client_label,
                        AppState.pick_config_client,
                        AppState.config_client_picker_open,
                        AppState.set_config_client_picker_open,
                        "Search TPP",
                    ),
                    columns="2",
                    spacing="3",
                    width="100%",
                ),
                field("Redirect URI *", AppState.form_config_redirect_uri, AppState.set_form_config_redirect_uri),
                rx.vstack(
                    rx.text("Account overview", size="2", weight="medium", color="#1c2430"),
                    rx.segmented_control.root(
                        rx.segmented_control.item("Carousel", value="carousel"),
                        rx.segmented_control.item("Table", value="table"),
                        value=AppState.form_config_account_mode,
                        on_change=AppState.set_form_config_account_mode,
                        size="2",
                        radius="large",
                    ),
                    spacing="2",
                    align="start",
                ),
                rx.button("Save configuration", on_click=AppState.save_configuration),
                spacing="4",
                width="100%",
                align="start",
            ),
            width="min(46rem, 100%)",
            padding="1.15rem 1.25rem",
            background="white",
            border="1px solid #e7eaf0",
            border_radius="16px",
            box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
            ),
            width="100%",
            flex="1",
            min_height="0",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        fill=True,
    )


def _auth_code_row(card) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(rx.cond(card["tpp"] != "", card["tpp"], "—"), size="2", weight="medium", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["user"] != "", card["user"], "—"), size="2", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["scope"] != "", card["scope"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["expires"] != "", card["expires"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["created"] != "", card["created"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        on_click=AppState.open_auth_code_detail(card["index"]),
        cursor="pointer",
        style={"borderBottom": "1px solid #f2f4f7"},
        _hover={"background": "#f4f6ff"},
    )


def _auth_code_list() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon("search", size=16, color="#98a2b3", position="absolute", left="0.9rem", top="0.85rem"),
                rx.input(
                    placeholder="Search TPP, user, scope or date",
                    value=AppState.auth_code_query,
                    on_change=AppState.set_auth_code_query,
                    width="100%",
                    size="3",
                    variant="surface",
                    radius="large",
                    color_scheme="indigo",
                    style={
                        "height": "2.7rem",
                        "paddingLeft": "2.4rem",
                        "background": "white",
                        "border": "1px solid #e4e7ec",
                        "boxShadow": "0 8px 24px rgba(16, 24, 40, 0.05)",
                        "color": "#1c2430",
                    },
                ),
                position="relative",
                width="100%",
            ),
            rx.cond(
                AppState.filtered_auth_code_cards.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                _user_table_head("TPP"),
                                _user_table_head("User"),
                                _user_table_head("Scope"),
                                _user_table_head("Expires"),
                                _user_table_head("Created"),
                            ),
                        ),
                        rx.table.body(rx.foreach(AppState.filtered_auth_code_cards, _auth_code_row)),
                        width="100%",
                        style={"borderCollapse": "separate", "borderSpacing": "0"},
                    ),
                    width="100%",
                    max_height="min(62vh, 36rem)",
                    overflow_y="auto",
                    background="white",
                    border="1px solid #e7eaf0",
                    border_radius="20px",
                    box_shadow="0 18px 50px rgba(16, 24, 40, 0.08)",
                ),
                rx.callout(
                    rx.cond(
                        AppState.auth_code_cards.length() > 0,
                        "No authorization codes match the search.",
                        "No authorization codes found.",
                    ),
                    color_scheme="gray",
                    width="100%",
                ),
            ),
            spacing="3",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="auto",
    )


def _auth_code_hero() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text("Authorization code", size="1", color="rgba(255,255,255,0.75)", weight="medium"),
                    rx.heading(
                        rx.cond(AppState.auth_code_detail_tpp != "", AppState.auth_code_detail_tpp, "Authorization code"),
                        size="6",
                        color="white",
                    ),
                    rx.text(
                        rx.cond(AppState.auth_code_detail_user != "", AppState.auth_code_detail_user, "User unavailable"),
                        size="3",
                        color="white",
                        weight="medium",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.badge("Valid", variant="surface", radius="full", size="2"),
                width="100%",
                align="center",
            ),
            width="100%",
            padding="1.35rem 1.5rem",
            background="linear-gradient(135deg, #312e81 0%, #4338ca 58%, #6366f1 100%)",
        ),
        rx.grid(
            _detail_fact("Scope", AppState.auth_code_detail_scope),
            _detail_fact("Created", AppState.auth_code_detail_created),
            _detail_fact("Expires", AppState.auth_code_detail_expires),
            _detail_fact("State", AppState.auth_code_detail_state),
            columns="2",
            spacing="4",
            width="100%",
            padding="1rem 1.5rem 1.15rem",
        ),
        width="100%",
        border="1px solid #e4e7ec",
        border_radius="18px",
        overflow="hidden",
        background="white",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _auth_code_detail() -> rx.Component:
    return rx.box(
        rx.vstack(
            _auth_code_hero(),
            rx.grid(
                _copy_widget("Authorization code", AppState.auth_code_detail_code),
                _copy_widget("Client ID", AppState.auth_code_detail_client_id),
                _copy_widget("Party ID", AppState.auth_code_detail_user_id),
                _copy_widget("Redirect URI", AppState.auth_code_detail_redirect),
                columns="2",
                spacing="3",
                width="100%",
            ),
            rx.text(AppState.auth_code_detail_status, size="2", color="#667085"),
            spacing="4",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        overflow_y="auto",
        display="flex",
        justify_content="center",
        padding_bottom="0.5rem",
    )


def _auth_codes_header() -> rx.Component:
    return rx.cond(
        AppState.auth_code_detail_open,
        rx.hstack(
            _accounts_icon("arrow-left", AppState.close_auth_code_detail, "Authorization codes"),
            rx.button(
                "Get Token",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="indigo",
                on_click=AppState.exchange_selected_auth_code,
            ),
            spacing="2",
            align="center",
        ),
        rx.fragment(),
    )


def auth_code_page() -> rx.Component:
    return page_shell(
        rx.cond(AppState.auth_code_detail_open, "Authorization code", "Authorization codes"),
        rx.box(
            rx.cond(AppState.auth_code_detail_open, _auth_code_detail(), _auth_code_list()),
            flex="1",
            min_height="0",
            width="100%",
            overflow="hidden",
        ),
        header_action=_auth_codes_header(),
        fill=True,
    )


def _registration_table_head(label: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.text(label, size="1", weight="medium", color="#667085", style={"letterSpacing": "0.04em"}),
        padding_y="0.75rem",
        padding_x="1rem",
        style={"background": "#f8fafc"},
    )


def _registration_row(card) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(card["name"], size="2", weight="medium", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(
                rx.cond(card["id"] != "", card["id"], "—"),
                size="2",
                color="#1c2430",
                style={
                    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                    "letterSpacing": "0.01em",
                },
            ),
            padding_y="0.85rem",
            padding_x="1rem",
            max_width="22rem",
        ),
        rx.table.cell(
            rx.cond(
                card["scopes"] != "",
                rx.badge(card["scopes"], variant="soft", color_scheme="indigo", radius="full", size="1"),
                rx.text("—", size="2", color="#98a2b3"),
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["registered"] != "", card["registered"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        on_click=AppState.open_registration_detail(card["index"]),
        cursor="pointer",
        style={"borderBottom": "1px solid #f2f4f7"},
        _hover={"background": "#f4f6ff"},
    )


def _registration_list() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon("search", size=16, color="#98a2b3", position="absolute", left="0.9rem", top="0.85rem"),
                rx.input(
                    placeholder="Search name, ID, scopes or date",
                    value=AppState.registration_query,
                    on_change=AppState.set_registration_query,
                    width="100%",
                    size="3",
                    variant="surface",
                    radius="large",
                    color_scheme="indigo",
                    style={
                        "height": "2.7rem",
                        "paddingLeft": "2.4rem",
                        "background": "white",
                        "border": "1px solid #e4e7ec",
                        "boxShadow": "0 8px 24px rgba(16, 24, 40, 0.05)",
                        "color": "#1c2430",
                    },
                ),
                position="relative",
                width="100%",
            ),
            rx.cond(
                AppState.filtered_registration_cards.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                _registration_table_head("Name"),
                                _registration_table_head("ID"),
                                _registration_table_head("Scopes"),
                                _registration_table_head("Registered"),
                            ),
                        ),
                        rx.table.body(rx.foreach(AppState.filtered_registration_cards, _registration_row)),
                        width="100%",
                        style={"borderCollapse": "separate", "borderSpacing": "0"},
                    ),
                    width="100%",
                    max_height="min(62vh, 36rem)",
                    overflow_y="auto",
                    background="white",
                    border="1px solid #e7eaf0",
                    border_radius="20px",
                    box_shadow="0 18px 50px rgba(16, 24, 40, 0.08)",
                ),
                rx.callout(
                    rx.cond(
                        AppState.registration_cards.length() > 0,
                        "No registrations match the search.",
                        "No registrations found.",
                    ),
                    color_scheme="gray",
                    width="100%",
                ),
            ),
            spacing="3",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="auto",
    )


def _copy_widget(label: str, value) -> rx.Component:
    filled = (value != "") & (value != "N/A")
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(label, size="2", weight="medium", color="#667085"),
                rx.spacer(),
                rx.button(
                    rx.icon("copy", size=14),
                    "Copy",
                    size="1",
                    variant="soft",
                    color_scheme="indigo",
                    radius="large",
                    disabled=~filled,
                    on_click=rx.set_clipboard(value),
                ),
                width="100%",
                align="center",
            ),
            rx.box(
                rx.text(
                    rx.cond(filled, value, "—"),
                    size="2",
                    color="#1c2430",
                    style={
                        "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                        "wordBreak": "break-all",
                        "lineHeight": "1.45",
                    },
                ),
                width="100%",
                max_height="7.5rem",
                overflow_y="auto",
            ),
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
        padding="1rem 1.1rem",
        background="white",
        border="1px solid #e7eaf0",
        border_radius="16px",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _registration_hero() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text("TPP", size="1", color="rgba(255,255,255,0.75)", weight="medium"),
                    rx.heading(AppState.registration_name, size="6", color="white"),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.cond(
                    AppState.registration_scope != "",
                    rx.badge(AppState.registration_scope, variant="surface", radius="full", size="2"),
                ),
                width="100%",
                align="center",
            ),
            width="100%",
            padding="1.35rem 1.5rem",
            background="linear-gradient(135deg, #312e81 0%, #4338ca 58%, #6366f1 100%)",
        ),
        rx.grid(
            _detail_fact("Registered", AppState.registration_registered),
            _detail_fact("Auth method", AppState.registration_auth_method),
            _detail_fact("Redirect URI", AppState.registration_redirect),
            _detail_fact("Grant types", AppState.registration_grants),
            columns="2",
            spacing="4",
            width="100%",
            padding="1rem 1.5rem 1.15rem",
        ),
        width="100%",
        border="1px solid #e4e7ec",
        border_radius="18px",
        overflow="hidden",
        background="white",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _registration_detail() -> rx.Component:
    return rx.box(
        rx.vstack(
            _registration_hero(),
            rx.grid(
                _copy_widget("Client ID", AppState.registration_client_id),
                _copy_widget("Client secret", AppState.registration_client_secret),
                _copy_widget("Registration access token", AppState.registration_access_token),
                _copy_widget("Basic auth header", AppState.registration_basic_auth),
                columns="2",
                spacing="3",
                width="100%",
            ),
            spacing="4",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        overflow_y="auto",
        display="flex",
        justify_content="center",
        padding_bottom="0.5rem",
    )


def _registration_create_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.vstack(
                    rx.dialog.title("Add new TPP"),
                    rx.text("Name and scope. The remaining fields come from the registration template.", size="2", color="#667085"),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.dialog.close(
                    rx.icon_button(rx.icon("x", size=16), size="2", variant="ghost", color_scheme="gray", radius="full"),
                ),
                width="100%",
                align="start",
            ),
            rx.vstack(
                _pay_field("Registration name", AppState.form_registration_name, AppState.set_form_registration_name),
                _pay_select("Scope", SCOPE_OPTIONS, AppState.form_registration_scope, AppState.set_form_registration_scope),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            size="3",
                            radius="large",
                            variant="soft",
                            color_scheme="gray",
                            style={"minWidth": "7rem"},
                        ),
                    ),
                    rx.button(
                        "Register TPP",
                        size="3",
                        radius="large",
                        on_click=AppState.submit_registration,
                        style={"minWidth": "9.5rem", "background": "#4f46e5", "color": "white"},
                    ),
                    width="100%",
                    spacing="3",
                    padding_top="0.35rem",
                    justify="end",
                ),
                spacing="3",
                width="100%",
                align="start",
            ),
            max_width="32rem",
            style={
                "borderRadius": "22px",
                "padding": "1.35rem 1.4rem 1.15rem",
                "border": "1px solid #e7eaf0",
                "boxShadow": "0 24px 60px rgba(16, 24, 40, 0.16)",
                "background": "white",
            },
        ),
        open=AppState.registration_create_open,
        on_open_change=AppState.set_registration_create_open,
    )


def _registration_delete_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Delete registration"),
            rx.text(
                "This deletes ",
                AppState.registration_name,
                " and cannot be undone.",
                size="2",
                color="#667085",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button("Cancel", size="2", radius="large", variant="soft", color_scheme="gray"),
                ),
                rx.button(
                    "Delete",
                    size="2",
                    radius="large",
                    color_scheme="red",
                    on_click=AppState.submit_delete_registration,
                ),
                spacing="2",
                justify="end",
                width="100%",
                margin_top="1rem",
            ),
            max_width="28rem",
        ),
        open=AppState.registration_delete_open,
        on_open_change=AppState.set_registration_delete_open,
    )


def _registrations_header() -> rx.Component:
    return rx.cond(
        AppState.registration_detail_open,
        rx.hstack(
            _accounts_icon("arrow-left", AppState.close_registration_detail, "Registrations"),
            rx.button(
                "Delete",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="red",
                on_click=AppState.open_registration_delete,
            ),
            spacing="2",
            align="center",
        ),
        rx.button(
            "Add new TPP",
            size="2",
            radius="large",
            on_click=AppState.open_create_registration,
            style={"background": "#4f46e5", "color": "white"},
        ),
    )


def registrations_page() -> rx.Component:
    return page_shell(
        rx.cond(AppState.registration_detail_open, "Registration detail", "Registrations"),
        rx.box(
            rx.cond(AppState.registration_detail_open, _registration_detail(), _registration_list()),
            flex="1",
            min_height="0",
            width="100%",
            overflow="hidden",
        ),
        _registration_create_dialog(),
        _registration_delete_dialog(),
        header_action=_registrations_header(),
        fill=True,
    )


def _token_row(card) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(rx.cond(card["tpp"] != "", card["tpp"], "—"), size="2", weight="medium", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["user"] != "", card["user"], "—"), size="2", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["scope"] != "", card["scope"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.badge(
                card["access"],
                variant="soft",
                radius="full",
                color_scheme=rx.cond(card["access"] == "Valid", "green", "red"),
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["created"] != "", card["created"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        on_click=AppState.open_token_detail(card["index"]),
        cursor="pointer",
        style={"borderBottom": "1px solid #f2f4f7"},
        _hover={"background": "#f4f6ff"},
    )


def _token_list() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon("search", size=16, color="#98a2b3", position="absolute", left="0.9rem", top="0.85rem"),
                rx.input(
                    placeholder="Search TPP, user, scope or date",
                    value=AppState.token_query,
                    on_change=AppState.set_token_query,
                    width="100%",
                    size="3",
                    variant="surface",
                    radius="large",
                    color_scheme="indigo",
                    style={
                        "height": "2.7rem",
                        "paddingLeft": "2.4rem",
                        "background": "white",
                        "border": "1px solid #e4e7ec",
                        "boxShadow": "0 8px 24px rgba(16, 24, 40, 0.05)",
                        "color": "#1c2430",
                    },
                ),
                position="relative",
                width="100%",
            ),
            rx.cond(
                AppState.filtered_token_cards.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                _user_table_head("TPP"),
                                _user_table_head("User"),
                                _user_table_head("Scope"),
                                _user_table_head("Access"),
                                _user_table_head("Created"),
                            ),
                        ),
                        rx.table.body(rx.foreach(AppState.filtered_token_cards, _token_row)),
                        width="100%",
                        style={"borderCollapse": "separate", "borderSpacing": "0"},
                    ),
                    width="100%",
                    max_height="min(62vh, 36rem)",
                    overflow_y="auto",
                    background="white",
                    border="1px solid #e7eaf0",
                    border_radius="20px",
                    box_shadow="0 18px 50px rgba(16, 24, 40, 0.08)",
                ),
                rx.callout(
                    rx.cond(
                        AppState.token_cards.length() > 0,
                        "No tokens match the search.",
                        "No tokens found.",
                    ),
                    color_scheme="gray",
                    width="100%",
                ),
            ),
            spacing="3",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="auto",
    )


def _token_hero() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text("Token", size="1", color="rgba(255,255,255,0.75)", weight="medium"),
                    rx.heading(
                        rx.cond(AppState.token_detail_tpp != "", AppState.token_detail_tpp, "Token"),
                        size="6",
                        color="white",
                    ),
                    rx.text(
                        rx.cond(AppState.token_detail_user != "", AppState.token_detail_user, "User unavailable"),
                        size="3",
                        color="white",
                        weight="medium",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.badge(
                    AppState.token_detail_access,
                    variant="surface",
                    radius="full",
                    size="2",
                ),
                width="100%",
                align="center",
            ),
            width="100%",
            padding="1.35rem 1.5rem",
            background="linear-gradient(135deg, #312e81 0%, #4338ca 58%, #6366f1 100%)",
        ),
        rx.grid(
            _detail_fact("Scope", AppState.token_detail_scope),
            _detail_fact("Created", AppState.token_detail_created),
            _detail_fact("Access expires", AppState.token_detail_expires),
            _detail_fact("Refresh created", AppState.token_detail_refresh_created),
            columns="2",
            spacing="4",
            width="100%",
            padding="1rem 1.5rem 1.15rem",
        ),
        width="100%",
        border="1px solid #e4e7ec",
        border_radius="18px",
        overflow="hidden",
        background="white",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _token_detail() -> rx.Component:
    return rx.box(
        rx.vstack(
            _token_hero(),
            rx.grid(
                _copy_widget("Client ID", AppState.token_client_id),
                _copy_widget("Party ID", AppState.token_detail_user_id),
                _copy_widget("Access token", AppState.token_access),
                _copy_widget("Refresh token", AppState.token_refresh),
                columns="2",
                spacing="3",
                width="100%",
            ),
            rx.cond(
                AppState.introspect_summary != "",
                rx.vstack(
                    pre_block("Introspection", AppState.introspect_summary),
                    rx.cond(AppState.introspect_json != "", json_block(AppState.introspect_json)),
                    spacing="3",
                    width="100%",
                ),
            ),
            spacing="4",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        overflow_y="auto",
        display="flex",
        justify_content="center",
        padding_bottom="0.5rem",
    )


def _token_revoke_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Revoke token"),
            rx.text(
                "This revokes the ",
                rx.cond(AppState.token_action_type == "Access", "access token", "refresh token"),
                " for ",
                AppState.token_detail_tpp,
                " and cannot be undone.",
                size="2",
                color="#667085",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button("Cancel", size="2", radius="large", variant="soft", color_scheme="gray"),
                ),
                rx.button(
                    "Revoke",
                    size="2",
                    radius="large",
                    color_scheme="red",
                    on_click=AppState.revoke_selected,
                ),
                spacing="2",
                justify="end",
                width="100%",
                margin_top="1rem",
            ),
            max_width="28rem",
        ),
        open=AppState.token_revoke_open,
        on_open_change=AppState.set_token_revoke_open,
    )


def _tokens_header() -> rx.Component:
    return rx.cond(
        AppState.token_detail_open,
        rx.hstack(
            _accounts_icon("arrow-left", AppState.close_token_detail, "Tokens"),
            rx.segmented_control.root(
                rx.segmented_control.item("Access", value="Access"),
                rx.segmented_control.item("Refresh", value="Refresh"),
                value=AppState.token_action_type,
                on_change=AppState.set_token_action_type,
                size="2",
                radius="large",
            ),
            rx.button(
                "Introspect",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="indigo",
                on_click=AppState.introspect_selected,
            ),
            rx.button(
                "Revoke",
                size="2",
                radius="large",
                variant="soft",
                color_scheme="red",
                on_click=AppState.open_token_revoke,
            ),
            spacing="2",
            align="center",
        ),
        rx.fragment(),
    )


def tokens_page() -> rx.Component:
    return page_shell(
        rx.cond(AppState.token_detail_open, "Token detail", "Tokens"),
        rx.box(
            rx.cond(AppState.token_detail_open, _token_detail(), _token_list()),
            flex="1",
            min_height="0",
            width="100%",
            overflow="hidden",
        ),
        _token_revoke_dialog(),
        header_action=_tokens_header(),
        fill=True,
    )


def _consent_row(card) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(rx.cond(card["owner"] != "", card["owner"], "—"), size="2", weight="medium", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["tpp"] != "", card["tpp"], "—"), size="2", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["scopes"] != "", card["scopes"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(rx.cond(card["valid_to"] != "", card["valid_to"], "—"), size="2", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(
                rx.cond(card["id"] != "", card["id"], "—"),
                size="2",
                color="#1c2430",
                style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"},
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        on_click=AppState.open_consent_detail(card["index"]),
        cursor="pointer",
        style={"borderBottom": "1px solid #f2f4f7"},
        _hover={"background": "#f4f6ff"},
    )


def _consent_list() -> rx.Component:
    table = rx.box(
        rx.vstack(
            rx.box(
                rx.icon("search", size=16, color="#98a2b3", position="absolute", left="0.9rem", top="0.85rem"),
                rx.input(
                    placeholder="Search owner, TPP, scopes or ID",
                    value=AppState.consent_query,
                    on_change=AppState.set_consent_query,
                    width="100%",
                    size="3",
                    variant="surface",
                    radius="large",
                    color_scheme="indigo",
                    style={
                        "height": "2.7rem",
                        "paddingLeft": "2.4rem",
                        "background": "white",
                        "border": "1px solid #e4e7ec",
                        "boxShadow": "0 8px 24px rgba(16, 24, 40, 0.05)",
                        "color": "#1c2430",
                    },
                ),
                position="relative",
                width="100%",
            ),
            rx.cond(
                AppState.filtered_consent_cards.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                _user_table_head("Owner"),
                                _user_table_head("TPP"),
                                _user_table_head("Scopes"),
                                _user_table_head("Valid to"),
                                _user_table_head("ID"),
                            ),
                        ),
                        rx.table.body(rx.foreach(AppState.filtered_consent_cards, _consent_row)),
                        width="100%",
                        style={"borderCollapse": "separate", "borderSpacing": "0"},
                    ),
                    width="100%",
                    max_height="min(62vh, 36rem)",
                    overflow_y="auto",
                    background="white",
                    border="1px solid #e7eaf0",
                    border_radius="20px",
                    box_shadow="0 18px 50px rgba(16, 24, 40, 0.08)",
                ),
                rx.callout(
                    rx.cond(
                        AppState.consent_cards.length() > 0,
                        "No consents match the search.",
                        "No consents found.",
                    ),
                    color_scheme="gray",
                    width="100%",
                ),
            ),
            spacing="3",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="auto",
    )
    return rx.cond(
        AppState.consent_status == "missing_context",
        rx.center(
            rx.callout("Select a TPP or a User.", color_scheme="gray", width="min(32rem, 100%)"),
            width="100%",
            height="100%",
        ),
        rx.cond(
            AppState.consent_status == "unavailable",
            rx.center(
                rx.callout("Service unavailable", color_scheme="orange", width="min(32rem, 100%)"),
                width="100%",
                height="100%",
            ),
            rx.cond(
                AppState.consent_status == "error",
                rx.center(
                    rx.callout(AppState.consent_status_text, color_scheme="red", width="min(40rem, 100%)"),
                    width="100%",
                    height="100%",
                ),
                table,
            ),
        ),
    )


def _consent_hero() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text("Consent", size="1", color="rgba(255,255,255,0.75)", weight="medium"),
                    rx.heading(
                        rx.cond(AppState.consent_detail_client != "", AppState.consent_detail_client, "Consent"),
                        size="6",
                        color="white",
                    ),
                    rx.text(
                        rx.cond(AppState.consent_detail_id != "", AppState.consent_detail_id, "ID unavailable"),
                        size="3",
                        color="white",
                        weight="medium",
                        style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", "letterSpacing": "0.03em"},
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.cond(
                    AppState.consent_detail_recalled != "",
                    rx.badge("Recalled", variant="surface", radius="full", size="2"),
                ),
                width="100%",
                align="center",
            ),
            width="100%",
            padding="1.35rem 1.5rem",
            background="linear-gradient(135deg, #312e81 0%, #4338ca 58%, #6366f1 100%)",
        ),
        rx.grid(
            _detail_fact("Owner", AppState.consent_detail_owner),
            _detail_fact("Valid from", AppState.consent_detail_valid_from),
            _detail_fact("Valid to", AppState.consent_detail_valid_to),
            rx.cond(
                AppState.consent_detail_recalled != "",
                _detail_fact("Recalled", AppState.consent_detail_recalled),
            ),
            columns="3",
            spacing="4",
            width="100%",
            padding="1rem 1.5rem 1.15rem",
        ),
        width="100%",
        border="1px solid #e4e7ec",
        border_radius="18px",
        overflow="hidden",
        background="white",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _consent_detail() -> rx.Component:
    return rx.box(
        rx.vstack(
            _consent_hero(),
            rx.grid(
                _copy_widget("Consent ID", AppState.consent_detail_id),
                _copy_widget("Owner ID", AppState.consent_detail_owner_id),
                _copy_widget("OAuth client ID", AppState.consent_detail_client_id),
                _copy_widget("Scopes", AppState.consent_detail_scopes),
                _copy_widget("Disponents", AppState.consent_detail_disponents),
                columns="2",
                spacing="3",
                width="100%",
            ),
            spacing="4",
            width="min(68rem, 100%)",
            align="center",
        ),
        width="100%",
        height="100%",
        min_height="0",
        overflow_y="auto",
        display="flex",
        justify_content="center",
        padding_bottom="0.5rem",
    )


def _consents_header() -> rx.Component:
    return rx.cond(
        AppState.consent_detail_open,
        _accounts_icon("arrow-left", AppState.close_consent_detail, "Consents"),
        rx.fragment(),
    )


def consents_page() -> rx.Component:
    return page_shell(
        rx.cond(AppState.consent_detail_open, "Consent detail", "Consents"),
        rx.box(
            rx.cond(AppState.consent_detail_open, _consent_detail(), _consent_list()),
            flex="1",
            min_height="0",
            width="100%",
            overflow="hidden",
        ),
        header_action=_consents_header(),
        fill=True,
    )


def _account_card(card) -> rx.Component:
    large = card["kind"] == "large"
    side = card["kind"] == "side"
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text("Account", size="1", color="rgba(255,255,255,0.72)", weight="medium"),
                rx.spacer(),
                rx.cond(
                    card["currency"] != "",
                    rx.box(
                        rx.text(card["currency"], size="1", weight="bold", color="white"),
                        background="rgba(255,255,255,0.18)",
                        border_radius="999px",
                        padding="0.15rem 0.6rem",
                    ),
                ),
                width="100%",
                align="center",
            ),
            rx.heading(
                card["name"],
                size=rx.cond(large, "6", rx.cond(side, "4", "5")),
                color="white",
                truncate=True,
                width="100%",
            ),
            rx.spacer(),
            rx.text(
                rx.cond(card["iban"] != "", card["iban"], "IBAN unavailable"),
                size=rx.cond(large, "4", rx.cond(side, "2", "3")),
                color="white",
                weight="medium",
                truncate=True,
                width="100%",
                style={"letterSpacing": "0.04em", "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"},
            ),
            rx.text("ID ", card["id"], size="1", color="rgba(255,255,255,0.75)"),
            spacing="2",
            width="100%",
            height="100%",
            align="start",
        ),
        on_click=AppState.open_account_detail(card["index"]),
        data_account_id=card["index"],
        width=rx.cond(large, "min(26rem, 34vw)", rx.cond(side, "min(15rem, 20vw)", "min(22rem, 28vw)")),
        height=rx.cond(large, "15.5rem", rx.cond(side, "11rem", "13.5rem")),
        padding="1.15rem 1.25rem",
        border_radius="22px",
        color="white",
        cursor="grab",
        background=card["gradient"],
        box_shadow=rx.cond(side, "0 8px 20px rgba(49, 46, 129, 0.16)", "0 18px 40px rgba(49, 46, 129, 0.28)"),
        opacity=rx.cond(side, "0.78", "1"),
        flex_shrink="0",
        style={"userSelect": "none", "transformOrigin": "top left"},
    )


def _carousel_arrow(direction: str) -> rx.Component:
    go_next = direction == "next"
    return rx.box(
        rx.cond(
            AppState.has_right_card if go_next else AppState.has_left_card,
            rx.icon_button(
                rx.icon("chevron-right" if go_next else "chevron-left", size=22),
                id="carousel-next" if go_next else "carousel-prev",
                on_click=AppState.carousel_next if go_next else AppState.carousel_prev,
                variant="soft",
                size="3",
                radius="full",
            ),
        ),
        width="3rem",
        display="flex",
        align_items="center",
        justify_content="center",
    )


_CAROUSEL_DRAG = """
(() => {
  const el = document.getElementById("account-stage");
  if (!el || el.dataset.dragBound === "1") return;
  el.dataset.dragBound = "1";
  let dragging = false;
  let moved = false;
  let startX = 0;
  let wheelLock = false;
  el.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    dragging = true;
    moved = false;
    startX = event.clientX;
  });
  el.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    if (Math.abs(event.clientX - startX) > 8) moved = true;
  });
  const finish = (event) => {
    if (!dragging) return;
    dragging = false;
    const dx = event.clientX - startX;
    if (dx <= -48) document.getElementById("carousel-next")?.click();
    else if (dx >= 48) document.getElementById("carousel-prev")?.click();
  };
  el.addEventListener("pointerup", finish);
  el.addEventListener("pointercancel", () => { dragging = false; });
  el.addEventListener("click", (event) => {
    if (!moved) return;
    if (event.target.closest && event.target.closest("#carousel-next, #carousel-prev")) return;
    event.preventDefault();
    event.stopPropagation();
    moved = false;
  }, true);
  el.addEventListener("wheel", (event) => {
    event.preventDefault();
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX) || wheelLock) return;
    const target = document.getElementById(event.deltaY > 0 ? "carousel-next" : "carousel-prev");
    if (!target) return;
    wheelLock = true;
    target.click();
    setTimeout(() => { wheelLock = false; }, 520);
  }, { passive: false });

  const motion = { duration: 460, easing: "cubic-bezier(0.22, 1, 0.36, 1)", fill: "both" };
  let pending = null;
  let generation = 0;
  let effects = [];
  const clearMotion = () => {
    effects.forEach((effect) => effect.cancel());
    effects = [];
    document.querySelectorAll(".carousel-ghost").forEach((ghost) => ghost.remove());
  };
  const snapshot = () => {
    const stage = document.getElementById("account-stage");
    if (!stage) return;
    clearMotion();
    pending = [...stage.querySelectorAll("[data-account-id]")].map((node) => ({
      id: node.dataset.accountId,
      rect: node.getBoundingClientRect(),
      clone: node.cloneNode(true),
    }));
  };
  const play = (direction) => {
    const stage = document.getElementById("account-stage");
    const before = pending;
    if (!stage || !before || !before.length) return false;
    const current = [...stage.querySelectorAll("[data-account-id]")];
    const seen = new Set(current.map((node) => node.dataset.accountId));
    const moved = current.some((node) => {
      const prev = before.find((item) => item.id === node.dataset.accountId);
      if (!prev) return true;
      const next = node.getBoundingClientRect();
      return Math.abs(next.left - prev.rect.left) > 1 || Math.abs(next.width - prev.rect.width) > 1;
    }) || current.length !== before.length;
    if (!moved) return false;
    pending = null;
    current.forEach((node) => {
      const prev = before.find((item) => item.id === node.dataset.accountId);
      const next = node.getBoundingClientRect();
      node.style.transformOrigin = "top left";
      if (!prev || !next.width || !next.height) {
        effects.push(node.animate([
          { transform: `translateX(${direction * 72}px)`, opacity: 0.45 },
          { transform: "none", opacity: 1 },
        ], motion));
        return;
      }
      const dx = prev.rect.left - next.left;
      const dy = prev.rect.top - next.top;
      effects.push(node.animate([
        { transform: `translate(${dx}px, ${dy}px) scale(${prev.rect.width / next.width}, ${prev.rect.height / next.height})` },
        { transform: "none" },
      ], motion));
    });
    before.filter((item) => !seen.has(item.id)).forEach((item) => {
      const ghost = item.clone;
      ghost.classList.add("carousel-ghost");
      ghost.style.position = "fixed";
      ghost.style.left = `${item.rect.left}px`;
      ghost.style.top = `${item.rect.top}px`;
      ghost.style.width = `${item.rect.width}px`;
      ghost.style.height = `${item.rect.height}px`;
      ghost.style.margin = "0";
      ghost.style.pointerEvents = "none";
      ghost.style.zIndex = "30";
      ghost.style.transformOrigin = "center center";
      document.body.appendChild(ghost);
      const effect = ghost.animate([
        { transform: "none", opacity: 1 },
        { transform: `translateX(${direction * -86}px) scale(0.9)`, opacity: 0 },
      ], motion);
      effect.onfinish = () => ghost.remove();
      effects.push(effect);
    });
    return true;
  };
  document.addEventListener("click", (event) => {
    const button = event.target.closest && event.target.closest("#carousel-next, #carousel-prev");
    if (!button) return;
    const direction = button.id === "carousel-next" ? 1 : -1;
    const run = ++generation;
    snapshot();
    const started = performance.now();
    const wait = () => {
      if (run !== generation) return;
      if (play(direction)) return;
      if (performance.now() - started < 1200) requestAnimationFrame(wait);
    };
    requestAnimationFrame(wait);
  }, true);
})();
"""


def _carousel_indicator() -> rx.Component:
    return rx.cond(
        AppState.account_cards.length() > 3,
        rx.hstack(
            rx.foreach(
                AppState.account_cards,
                lambda card: rx.box(
                    width=rx.cond(
                        AppState.account_carousel_index.to_string() == card["index"],
                        "1.45rem",
                        "0.45rem",
                    ),
                    height="0.45rem",
                    border_radius="999px",
                    background=rx.cond(
                        AppState.account_carousel_index.to_string() == card["index"],
                        "#4f46e5",
                        "#d0d5dd",
                    ),
                    style={"transition": "width 0.2s ease, background 0.2s ease"},
                ),
            ),
            spacing="2",
            justify="center",
            width="100%",
        ),
    )


def _account_table_row(card) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(card["id"], size="1", weight="medium", color="#667085"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(
                rx.cond(card["number"] != "", card["number"], "—"),
                size="2",
                color="#1c2430",
                style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"},
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(
                rx.cond(card["iban"] != "", card["iban"], "—"),
                size="2",
                color="#1c2430",
                style={
                    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                    "letterSpacing": "0.03em",
                },
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.text(card["name"], size="2", weight="medium", color="#1c2430"),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        rx.table.cell(
            rx.cond(
                card["currency"] != "",
                rx.badge(card["currency"], variant="soft", color_scheme="indigo", radius="full", size="1"),
                rx.text("—", size="2", color="#98a2b3"),
            ),
            padding_y="0.85rem",
            padding_x="1rem",
        ),
        on_click=AppState.open_account_detail(card["index"]),
        cursor="pointer",
        style={"borderBottom": "1px solid #f2f4f7"},
        _hover={"background": "#f4f6ff"},
    )


def _account_table_head(label: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.text(label, size="1", weight="medium", color="#667085", style={"letterSpacing": "0.04em"}),
        padding_y="0.75rem",
        padding_x="1rem",
        style={"background": "#f8fafc"},
    )


def _account_table() -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.icon("search", size=16, color="#98a2b3", position="absolute", left="0.9rem", top="0.85rem"),
            rx.input(
                placeholder="Search ID, account number, IBAN, name or currency",
                value=AppState.account_table_query,
                on_change=AppState.set_account_table_query,
                width="100%",
                size="3",
                variant="surface",
                radius="large",
                color_scheme="indigo",
                style={
                    "height": "2.7rem",
                    "paddingLeft": "2.4rem",
                    "background": "white",
                    "border": "1px solid #e4e7ec",
                    "boxShadow": "0 8px 24px rgba(16, 24, 40, 0.05)",
                    "color": "#1c2430",
                },
            ),
            position="relative",
            width="100%",
        ),
        rx.cond(
            AppState.filtered_account_cards.length() > 0,
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            _account_table_head("ID"),
                            _account_table_head("Account number"),
                            _account_table_head("IBAN"),
                            _account_table_head("Name"),
                            _account_table_head("Currency"),
                        ),
                    ),
                    rx.table.body(rx.foreach(AppState.filtered_account_cards, _account_table_row)),
                    width="100%",
                    style={"borderCollapse": "separate", "borderSpacing": "0"},
                ),
                width="100%",
                max_height="min(68vh, 38rem)",
                overflow_y="auto",
                background="white",
                border="1px solid #e7eaf0",
                border_radius="20px",
                box_shadow="0 18px 50px rgba(16, 24, 40, 0.08)",
            ),
            rx.callout("No accounts match the search.", color_scheme="gray", width="100%"),
        ),
        spacing="3",
        width="min(68rem, 92%)",
        align="center",
    )


def _account_carousel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                _carousel_arrow("prev"),
                rx.box(
                    rx.hstack(
                        rx.foreach(AppState.carousel_slots, _account_card),
                        spacing="4",
                        align="center",
                        justify="center",
                    ),
                    id="account-stage",
                    on_mount=rx.call_script(_CAROUSEL_DRAG),
                    cursor="grab",
                    max_width="100%",
                    overflow="hidden",
                ),
                _carousel_arrow("next"),
                spacing="3",
                align="center",
                justify="center",
                width="100%",
            ),
            _carousel_indicator(),
            spacing="5",
            align="center",
            justify="center",
            width="100%",
        ),
        position="relative",
        width="100%",
        height="100%",
        min_height="0",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="hidden",
    )


def _detail_fact(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="gray", weight="medium"),
        rx.text(rx.cond(value != "", value, "—"), size="2", weight="medium", color="#1c2430"),
        spacing="1",
        align="start",
        min_width="0",
    )


def _account_detail_hero() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text(
                        rx.cond(AppState.account_detail_product != "", AppState.account_detail_product, "Account"),
                        size="1",
                        color="rgba(255,255,255,0.75)",
                        weight="medium",
                    ),
                    rx.heading(AppState.account_detail_name, size="6", color="white"),
                    rx.text(
                        rx.cond(AppState.account_detail_iban != "", AppState.account_detail_iban, "IBAN unavailable"),
                        size="4",
                        color="white",
                        weight="medium",
                        style={"letterSpacing": "0.06em", "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"},
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.cond(
                        AppState.account_detail_currency != "",
                        rx.text(AppState.account_detail_currency, size="2", weight="bold", color="white"),
                    ),
                    rx.cond(
                        AppState.available_balance_amount != "",
                        rx.text(AppState.available_balance_amount, size="6", weight="bold", color="white"),
                    ),
                    spacing="1",
                    align="end",
                ),
                width="100%",
                align="start",
            ),
            width="100%",
            padding="1.35rem 1.5rem",
            background=AppState.account_detail_gradient,
        ),
        rx.grid(
            _detail_fact("Account number", AppState.account_detail_number),
            _detail_fact("Bank code", AppState.account_detail_bank),
            _detail_fact("BIC", AppState.account_detail_bic),
            _detail_fact("Country", AppState.account_detail_country),
            _detail_fact("Account ID", AppState.account_detail_id),
            _detail_fact("Relationship", AppState.account_detail_owner),
            columns="4",
            spacing="4",
            width="100%",
            padding="1rem 1.5rem 0.85rem",
        ),
        rx.cond(
            AppState.other_balances.length() > 0,
            rx.box(
                rx.foreach(
                    AppState.other_balances,
                    lambda item: _detail_fact(item["label"], item["value"]),
                ),
                display="flex",
                flex_wrap="wrap",
                gap="1rem 1.5rem",
                width="100%",
                padding="0.15rem 1.5rem 1.15rem",
            ),
        ),
        rx.cond(
            (AppState.available_balance_amount == "") & (AppState.account_balance_note != ""),
            rx.hstack(
                rx.text(AppState.account_balance_note, size="2", color="gray"),
                rx.spacer(),
                rx.button("Refresh", size="1", variant="ghost", on_click=AppState.fetch_account_balance),
                width="100%",
                align="center",
                padding="0 1.5rem 1rem",
            ),
        ),
        width="100%",
        border="1px solid #e4e7ec",
        border_radius="18px",
        overflow="hidden",
        background="white",
        box_shadow="0 10px 28px rgba(16, 24, 40, 0.06)",
    )


def _pay_label(text: str) -> rx.Component:
    return rx.text(text, size="1", weight="medium", color="#667085")


def _pay_field(label: str, value, on_change, **props) -> rx.Component:
    return rx.vstack(
        _pay_label(label),
        rx.input(
            value=value,
            on_change=on_change,
            width="100%",
            size="3",
            variant="surface",
            radius="large",
            color_scheme="indigo",
            style={
                "height": "2.6rem",
                "background": "#f8fafc",
                "border": "1px solid #e4e7ec",
                "boxShadow": "none",
                "color": "#1c2430",
            },
            _focus={
                "background": "white",
                "border": "1px solid #6366f1",
                "boxShadow": "0 0 0 3px rgba(99, 102, 241, 0.16)",
            },
            **props,
        ),
        spacing="1",
        width="100%",
        align="start",
    )


def _pay_select(label: str, items, value, on_change, placeholder: str = "Select") -> rx.Component:
    return rx.vstack(
        _pay_label(label),
        rx.select.root(
            rx.select.trigger(
                placeholder=placeholder,
                width="100%",
                radius="large",
                variant="surface",
                color_scheme="indigo",
                style={
                    "height": "2.6rem",
                    "background": "#f8fafc",
                    "border": "1px solid #e4e7ec",
                    "boxShadow": "none",
                    "color": "#1c2430",
                    "cursor": "pointer",
                },
            ),
            rx.select.content(
                rx.select.group(
                    rx.foreach(items, lambda item: rx.select.item(item, value=item)),
                ),
                position="popper",
                side_offset=6,
                style={
                    "background": "white",
                    "border": "1px solid #e4e7ec",
                    "borderRadius": "14px",
                    "boxShadow": "0 16px 40px rgba(16, 24, 40, 0.12)",
                    "maxHeight": "16rem",
                },
            ),
            value=value,
            on_change=on_change,
            size="3",
            width="100%",
        ),
        spacing="1",
        width="100%",
        align="start",
    )


def _pay_section(title: str) -> rx.Component:
    return rx.text(title, size="2", weight="bold", color="#1c2430", padding_top="0.15rem")


def _payment_form() -> rx.Component:
    creditor = rx.cond(
        AppState.pay_creditor_options.length() > 0,
        _pay_select(
            "Creditor account",
            AppState.pay_creditor_options,
            AppState.pay_creditor_label,
            AppState.select_creditor_account,
            placeholder="Choose an account",
        ),
        _pay_field(
            "Creditor account",
            "",
            AppState.set_pay_creditor_label,
            disabled=True,
            placeholder="No other saved accounts",
        ),
    )
    return rx.vstack(
        _pay_section("Payment"),
        rx.grid(
            _pay_field("Identification", AppState.pay_instruction_id, AppState.set_pay_instruction_id),
            _pay_field("Amount", AppState.pay_amount, AppState.set_pay_amount),
            _pay_field("Currency", AppState.pay_currency, AppState.set_pay_currency),
            _pay_field("Execution date", AppState.pay_date, AppState.set_pay_date, type="date"),
            columns="2",
            spacing="3",
            width="100%",
        ),
        _pay_section("Creditor"),
        rx.grid(
            creditor,
            _pay_field("Creditor currency", AppState.pay_creditor_currency, AppState.set_pay_creditor_currency),
            columns="2",
            spacing="3",
            width="100%",
        ),
        _pay_section("Reference"),
        rx.grid(
            _pay_field("Variable symbol", AppState.pay_vs, AppState.set_pay_vs),
            _pay_field("Specific symbol", AppState.pay_ss, AppState.set_pay_ss),
            _pay_field("Constant symbol", AppState.pay_ks, AppState.set_pay_ks),
            columns="3",
            spacing="3",
            width="100%",
        ),
        _pay_field("Message", AppState.pay_unstructured, AppState.set_pay_unstructured),
        rx.box(
            _pay_select("Priority", PRIORITY_OPTIONS, AppState.pay_priority, AppState.set_pay_priority),
            width="50%",
            padding_right="0.45rem",
        ),
        rx.hstack(
            rx.cond(
                AppState.pay_edit_index != "",
                rx.button(
                    "Delete",
                    size="3",
                    radius="large",
                    variant="soft",
                    color_scheme="red",
                    on_click=AppState.delete_draft_payment,
                ),
            ),
            rx.spacer(),
            rx.dialog.close(
                rx.button(
                    "Cancel",
                    size="3",
                    radius="large",
                    variant="soft",
                    color_scheme="gray",
                    style={"minWidth": "7rem"},
                ),
            ),
            rx.button(
                rx.cond(AppState.pay_edit_index != "", "Send payment", "Create payment"),
                size="3",
                radius="large",
                on_click=AppState.submit_payment,
                style={
                    "minWidth": "9.5rem",
                    "background": "#4f46e5",
                    "color": "white",
                },
            ),
            width="100%",
            spacing="3",
            padding_top="0.35rem",
            justify="end",
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def _sheet_cell(value, color="#1c2430") -> rx.Component:
    return rx.table.cell(
        rx.text(
            value,
            size="1",
            width="100%",
            text_align="center",
            color=color,
            style={"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
        ),
        padding_y="0",
        overflow="hidden",
        style={"height": "2.15rem", "textAlign": "center", "verticalAlign": "middle"},
    )


def _sheet_head(label: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.text(label, size="1", weight="medium", width="100%", text_align="center"),
        padding_y="0",
        style={"height": "2.15rem", "textAlign": "center"},
    )


def _status_scheme(value):
    return rx.match(
        value,
        ("COMPLETED", "green"),
        ("BOOK", "green"),
        ("ACSC", "green"),
        ("ASCS", "green"),
        ("ACWP", "green"),
        ("AUTHORIZATION_REQUIRED", "orange"),
        ("NAUT", "orange"),
        ("RJCT", "red"),
        ("CANC", "red"),
        ("DRAFT", "yellow"),
        "gray",
    )


def _status_cell(value) -> rx.Component:
    return rx.table.cell(
        rx.center(
            rx.cond(
                value != "",
                rx.badge(value, variant="soft", size="1", color_scheme=_status_scheme(value)),
                rx.text(""),
            ),
            width="100%",
        ),
        padding_y="0",
        style={"height": "2.15rem", "textAlign": "center", "verticalAlign": "middle"},
    )


def _tx_row(item) -> rx.Component:
    amount_color = rx.cond(
        item["tone"] == "credit",
        "#15803d",
        rx.cond(item["tone"] == "debit", "#b91c1c", "#1c2430"),
    )
    row_background = rx.cond(
        item["tone"] == "credit",
        "#f0fdf4",
        rx.cond(item["tone"] == "debit", "#fef2f2", "white"),
    )
    return rx.table.row(
        _sheet_cell(item["amount"], amount_color),
        _sheet_cell(item["bookingDate"]),
        _sheet_cell(item["identification"]),
        _sheet_cell(item["counterparty"]),
        _sheet_cell(item["counterpartyName"]),
        _status_cell(item["status"]),
        on_double_click=AppState.show_tx_detail(item["index"]),
        style={"height": "2.15rem", "background": row_background},
        _hover={"background": "#e8eefc"},
    )


def _pay_row(item) -> rx.Component:
    amount_color = rx.cond(
        item["tone"] == "settled",
        "#15803d",
        rx.cond(item["tone"] == "cancelled", "#b91c1c", rx.cond(item["tone"] == "draft", "#a16207", rx.cond(item["tone"] == "other", "#6b7280", "#1c2430"))),
    )
    row_background = rx.cond(
        item["tone"] == "settled",
        "#f0fdf4",
        rx.cond(item["tone"] == "cancelled", "#fef2f2", rx.cond(item["tone"] == "draft", "#fef9c3", rx.cond(item["tone"] == "other", "#f3f4f6", "white"))),
    )
    return rx.table.row(
        _sheet_cell(item["amount"], amount_color),
        _sheet_cell(item["requestedExecutionDate"]),
        _sheet_cell(item["instructionIdentification"]),
        _sheet_cell(item["creditorIban"]),
        _status_cell(item["status"]),
        on_double_click=AppState.open_payment_row(item["index"]),
        style={"height": "2.15rem", "background": row_background},
        _hover={"background": "#e8eefc"},
    )


def _fixed_table(headers: list[str], rows, row_builder) -> rx.Component:
    return rx.table.root(
        rx.table.header(rx.table.row(*[_sheet_head(label) for label in headers])),
        rx.table.body(rx.foreach(rows, row_builder)),
        width="100%",
        style={"tableLayout": "fixed"},
    )


def _pager(label, has_prev, on_prev, has_next, on_next) -> rx.Component:
    return rx.hstack(
        rx.icon_button(
            rx.icon("chevron-left", size=14),
            size="1",
            variant="ghost",
            on_click=on_prev,
            disabled=~has_prev,
        ),
        rx.text(label, size="1", color="gray", min_width="3.2rem", text_align="center"),
        rx.icon_button(
            rx.icon("chevron-right", size=14),
            size="1",
            variant="ghost",
            on_click=on_next,
            disabled=~has_next,
        ),
        spacing="1",
        align="center",
    )


def _list_panel(title: str, actions: rx.Component, table: rx.Component, note) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(title, size="4"),
                rx.spacer(),
                actions,
                width="100%",
                align="center",
            ),
            rx.text(note, size="1", color="gray", height="1.1rem"),
            table,
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
        min_width="0",
        padding="1.15rem 1.25rem",
        border="1px solid #e4e7ec",
        border_radius="16px",
        background="white",
    )


def _modal_fact(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="gray"),
        rx.text(rx.cond(value != "", value, "—"), size="2"),
        spacing="0",
        align="start",
        min_width="9rem",
    )


def _detail_dialog(title: str, is_open, on_open, facts: list[rx.Component], detail) -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(title),
            rx.flex(*facts, wrap="wrap", gap="0.85rem 1.25rem", width="100%"),
            rx.box(
                rx.text(detail, size="1", white_space="pre-wrap"),
                width="100%",
                max_height="16rem",
                overflow_y="auto",
                margin_top="1rem",
                padding="0.75rem",
                background="#f8fafc",
                border_radius="10px",
                font_family="monospace",
            ),
            rx.dialog.close(rx.button("Close", variant="soft", margin_top="1rem")),
            max_width="44rem",
        ),
        open=is_open,
        on_open_change=on_open,
    )


def _account_detail_page() -> rx.Component:
    transactions = _list_panel(
        "Transactions",
        rx.hstack(
            _pager(
                AppState.tx_page_label,
                AppState.tx_has_prev,
                AppState.tx_page_prev,
                AppState.tx_has_next,
                AppState.tx_page_next,
            ),
            rx.icon_button(
                rx.icon("refresh-cw", size=14),
                size="1",
                variant="ghost",
                on_click=AppState.refresh_account_transactions,
            ),
            rx.icon_button(
                rx.icon("maximize-2", size=14),
                size="1",
                variant="ghost",
                on_click=AppState.open_tx_fullscreen,
            ),
            spacing="1",
            align="center",
        ),
        _fixed_table(
            ["Amount", "Booking date", "Identification", "Counterparty", "Counterparty name", "Status"],
            AppState.tx_page_rows,
            _tx_row,
        ),
        rx.cond(AppState.tx_records.length() == 0, "No transactions for this account.", ""),
    )
    payments = _list_panel(
        "Payments",
        rx.hstack(
            _pager(
                AppState.pay_page_label,
                AppState.pay_has_prev,
                AppState.pay_page_prev,
                AppState.pay_has_next,
                AppState.pay_page_next,
            ),
            rx.icon_button(
                rx.icon("refresh-cw", size=14),
                size="1",
                variant="ghost",
                on_click=AppState.refresh_payments,
            ),
            rx.button("New payment", size="1", variant="soft", on_click=AppState.open_pay_form),
            spacing="1",
            align="center",
        ),
        _fixed_table(
            ["Amount", "Date", "Identification", "Counterparty", "Status"],
            AppState.pay_page_rows,
            _pay_row,
        ),
        rx.cond(AppState.account_payment_records.length() == 0, "No payments from this account.", ""),
    )
    return rx.box(
        rx.vstack(
            _account_detail_hero(),
            rx.grid(transactions, payments, columns="2", spacing="4", width="100%"),
            _detail_dialog(
                "Transaction",
                AppState.tx_detail_open,
                AppState.set_tx_detail_open,
                [
                    _modal_fact("Amount", AppState.selected_tx["amount"]),
                    _modal_fact("Booking date", AppState.selected_tx["bookingDate"]),
                    _modal_fact("Identification", AppState.selected_tx["identification"]),
                    _modal_fact("Counterparty", AppState.selected_tx["counterparty"]),
                    _modal_fact("Counterparty name", AppState.selected_tx["counterpartyName"]),
                    _modal_fact("Direction", AppState.selected_tx["creditDebitIndicator"]),
                    _modal_fact("Status", AppState.selected_tx["status"]),
                    _modal_fact("Note", AppState.selected_tx["note"]),
                ],
                AppState.selected_tx["detail"],
            ),
            rx.dialog.root(
                rx.dialog.content(
                    rx.dialog.title("Payment"),
                    rx.flex(
                        _modal_fact("Amount", AppState.selected_payment["amount"]),
                        _modal_fact("Execution date", AppState.selected_payment["requestedExecutionDate"]),
                        _modal_fact("Status", AppState.selected_payment["status"]),
                        _modal_fact("Instruction", AppState.selected_payment["instructionIdentification"]),
                        _modal_fact("Transaction id", AppState.selected_payment["transactionIdentification"]),
                        _modal_fact("Created", AppState.selected_payment["dateCreated"]),
                        _modal_fact("Code", AppState.selected_payment["code"]),
                        _modal_fact("Priority", AppState.selected_payment["instructionPriority"]),
                        _modal_fact("Sign id", AppState.selected_payment["signId"]),
                        _modal_fact("Party ID", AppState.selected_payment["partyId"]),
                        _modal_fact("Account", AppState.selected_payment["debtorAccountId"]),
                        _modal_fact("Debtor IBAN", AppState.selected_payment["debtorIban"]),
                        _modal_fact("Creditor IBAN", AppState.selected_payment["creditorIban"]),
                        wrap="wrap",
                        gap="0.85rem 1.25rem",
                        width="100%",
                    ),
                    rx.box(
                        rx.text(
                            rx.cond(
                                AppState.pay_action_output != "",
                                AppState.pay_action_output,
                                AppState.selected_payment["detail"],
                            ),
                            size="1",
                            white_space="pre-wrap",
                        ),
                        width="100%",
                        max_height="16rem",
                        overflow_y="auto",
                        margin_top="1rem",
                        padding="0.75rem",
                        background="#f8fafc",
                        border_radius="10px",
                        font_family="monospace",
                    ),
                    rx.hstack(
                        rx.button(
                            "Detail",
                            variant="soft",
                            on_click=AppState.run_selected_payment_action("detail"),
                        ),
                        rx.button(
                            "Status",
                            variant="soft",
                            on_click=AppState.run_selected_payment_action("status"),
                        ),
                        rx.cond(
                            AppState.payment_can_authorize,
                            rx.button(
                                "Authorize",
                                on_click=AppState.run_selected_payment_action("authorize"),
                            ),
                            rx.fragment(),
                        ),
                        rx.cond(
                            AppState.payment_can_delete,
                            rx.button(
                                "Delete",
                                color_scheme="red",
                                variant="soft",
                                on_click=AppState.run_selected_payment_action("delete"),
                            ),
                            rx.fragment(),
                        ),
                        rx.dialog.close(rx.button("Close", variant="soft")),
                        spacing="2",
                        margin_top="1rem",
                        align="center",
                    ),
                    max_width="44rem",
                ),
                open=AppState.pay_detail_open,
                on_open_change=AppState.set_pay_detail_open,
            ),
            rx.dialog.root(
                rx.dialog.content(
                    rx.hstack(
                        rx.vstack(
                            rx.dialog.title(rx.cond(AppState.pay_edit_index != "", "Edit payment", "New payment")),
                            rx.text("Domestic payment from the open account", size="2", color="#667085"),
                            spacing="1",
                            align="start",
                        ),
                        rx.spacer(),
                        rx.dialog.close(
                            rx.icon_button(
                                rx.icon("x", size=16),
                                size="2",
                                variant="ghost",
                                color_scheme="gray",
                                radius="full",
                            ),
                        ),
                        width="100%",
                        align="start",
                    ),
                    _payment_form(),
                    max_width="42rem",
                    style={
                        "borderRadius": "22px",
                        "padding": "1.35rem 1.4rem 1.15rem",
                        "border": "1px solid #e7eaf0",
                        "boxShadow": "0 24px 60px rgba(16, 24, 40, 0.16)",
                        "background": "white",
                    },
                ),
                open=AppState.pay_form_open,
                on_open_change=AppState.set_pay_form_open,
            ),
            rx.dialog.root(
                rx.dialog.content(
                    rx.hstack(
                        rx.dialog.title("Transactions"),
                        rx.spacer(),
                        _pager(
                            AppState.tx_page_label,
                            AppState.tx_has_prev,
                            AppState.tx_page_prev,
                            AppState.tx_has_next,
                            AppState.tx_page_next,
                        ),
                        rx.dialog.close(
                            rx.icon_button(rx.icon("x", size=16), size="1", variant="ghost"),
                        ),
                        width="100%",
                        align="center",
                    ),
                    _fixed_table(
                        ["Amount", "Booking date", "Identification", "Counterparty", "Counterparty name", "Status"],
                        AppState.tx_page_rows,
                        _tx_row,
                    ),
                    width="94vw",
                    max_width="94vw",
                ),
                open=AppState.tx_fullscreen,
                on_open_change=AppState.set_tx_fullscreen,
            ),
            spacing="4",
            width="100%",
            align="start",
            padding_bottom="1.5rem",
        ),
        width="100%",
        flex="1",
        min_height="0",
        overflow_y="auto",
    )


def _accounts_icon(icon_name: str, on_click, tooltip: str) -> rx.Component:
    return rx.tooltip(
        rx.button(
            rx.icon(icon_name, size=14),
            on_click=on_click,
            variant="solid",
            border_radius="999px",
            width="2.05rem",
            height="2.05rem",
            padding="0",
        ),
        content=tooltip,
    )


def _accounts_header_icons() -> rx.Component:
    return rx.hstack(
        rx.cond(
            ~AppState.account_detail_open,
            rx.segmented_control.root(
                rx.segmented_control.item("Carousel", value="carousel"),
                rx.segmented_control.item("Table", value="table"),
                value=AppState.account_list_mode,
                on_change=AppState.set_account_list_mode,
                size="2",
                radius="large",
            ),
        ),
        rx.cond(
            AppState.account_detail_open,
            _accounts_icon("arrow-left", AppState.close_account_detail, "Accounts"),
        ),
        _accounts_icon("refresh-cw", AppState.refresh_accounts_view, "Refresh"),
        _accounts_icon("database", AppState.save_loaded_accounts, "Save accounts"),
        rx.box(
            _accounts_icon("scroll-text", AppState.toggle_log, "Log"),
            rx.cond(
                AppState.account_logs.length() > 0,
                rx.badge(
                    AppState.account_logs.length(),
                    position="absolute",
                    top="-0.35rem",
                    right="-0.35rem",
                    color_scheme="red",
                    variant="solid",
                ),
            ),
            position="relative",
        ),
        spacing="1",
        align="center",
        margin_right="1.25rem",
    )


def accounts_page() -> rx.Component:
    accounts_tab = rx.cond(
        AppState.account_status == "missing_context",
        rx.fragment(),
        rx.cond(
            AppState.account_status == "unavailable",
            rx.callout("Service unavailable", color_scheme="orange", width="100%"),
            rx.cond(
                AppState.account_status == "needs_auth",
                rx.vstack(
                    rx.callout(AppState.account_status_text, color_scheme="red", width="100%"),
                    rx.button("Authorize", on_click=AppState.authorize),
                    spacing="3",
                    align="start",
                ),
            rx.box(
                rx.cond(
                    AppState.account_cards.length() > 0,
                    rx.cond(
                        AppState.account_list_mode == "table",
                        _account_table(),
                        _account_carousel(),
                    ),
                    rx.callout("No accounts found for this user.", color_scheme="gray", width="100%"),
                ),
                width="100%",
                height="100%",
                min_height="0",
                display="flex",
                align_items="center",
                justify_content="center",
                overflow=rx.cond(AppState.account_list_mode == "table", "auto", "hidden"),
            ),
            ),
        ),
    )
    return page_shell(
        rx.cond(AppState.account_detail_open, "Account detail", "Accounts"),
        rx.cond(AppState.account_detail_open, _account_detail_page(), accounts_tab),
        header_action=_accounts_header_icons(),
        fill=True,
    )


def _process_wait(message) -> rx.Component:
    return rx.box(
        rx.center(
            rx.box(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text(message, size="3", weight="medium", color="#1c2430"),
                    spacing="3",
                    align="center",
                ),
                padding="1.5rem 1.85rem",
                background="rgba(255, 255, 255, 0.58)",
                border="1px solid rgba(255, 255, 255, 0.85)",
                border_radius="18px",
                box_shadow="0 16px 40px rgba(49, 46, 129, 0.12)",
                style={"backdropFilter": "blur(16px)", "WebkitBackdropFilter": "blur(16px)"},
            ),
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        flex="1",
        min_height="0",
        style={
            "background": "radial-gradient(circle at 50% 46%, rgba(79, 70, 229, 0.14), rgba(243, 245, 248, 0.94) 46%)",
            "backdropFilter": "blur(12px)",
            "WebkitBackdropFilter": "blur(12px)",
        },
    )


def app_page() -> rx.Component:
    return rx.box(
        rx.hstack(
            sidebar(),
            rx.box(
                rx.cond(
                    AppState.page_loading,
                    _process_wait(AppState.page_loading_message),
                    rx.match(
                        AppState.current_page,
                        ("dashboard", dashboard_page()),
                        ("accounts", accounts_page()),
                        ("registrations", registrations_page()),
                        ("users", users_page()),
                        ("tokens", tokens_page()),
                        ("consents", consents_page()),
                        ("configuration", configuration_page()),
                        ("auth-code", auth_code_page()),
                        dashboard_page(),
                    ),
                ),
                flex="1",
                min_width="0",
                height="100vh",
                padding="1.5rem 1.75rem",
                overflow_y=rx.cond(
                    (AppState.current_page == "accounts")
                    | (AppState.current_page == "registrations")
                    | (AppState.current_page == "users")
                    | (AppState.current_page == "consents")
                    | (AppState.current_page == "tokens")
                    | (AppState.current_page == "auth-code"),
                    "hidden",
                    "auto",
                ),
                display="flex",
                flex_direction="column",
            ),
            width="100%",
            height="100vh",
            spacing="0",
            align="start",
        ),
        log_panel(),
        notice_toasts(),
        width="100%",
        height="100vh",
    )
