"""Shared Reflex layout."""

import reflex as rx

from psd2_app.state import AppState

NAV_ITEMS = [
    ("Dashboard", "dashboard"),
    ("Accounts", "accounts"),
    ("Registrations", "registrations"),
    ("Users", "users"),
    ("Tokens", "tokens"),
    ("Consents", "consents"),
    ("Configuration", "configuration"),
    ("Authorization Code", "auth-code"),
]


def field(label: str, value, on_change, **props) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        rx.input(value=value, on_change=on_change, width="100%", **props),
        spacing="1",
        width="100%",
        align="start",
    )


def dropdown(label: str, items, value, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        rx.select(items, value=value, on_change=on_change, width="100%", size="2"),
        spacing="1",
        width="100%",
        align="start",
    )


def _picker_option(item, selected, on_pick) -> rx.Component:
    active = selected == item
    return rx.box(
        rx.hstack(
            rx.cond(
                active,
                rx.icon("check", size=14, color="#4338ca"),
                rx.box(width="14px", height="14px"),
            ),
            rx.text(
                rx.cond(item == "None", "No selection", item),
                size="2",
                weight=rx.cond(active, "medium", "regular"),
                white_space="normal",
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        on_click=on_pick(item),
        width="100%",
        padding="0.45rem 0.5rem",
        border_radius="8px",
        cursor="pointer",
        background=rx.cond(active, "#eef2ff", "transparent"),
        _hover={"background": rx.cond(active, "#e4e9ff", "#f4f6fb")},
    )


def context_picker(
    caption: str,
    icon: str,
    placeholder: str,
    name,
    item_id,
    query,
    on_query,
    options,
    selected,
    on_pick,
    is_open,
    on_open,
    search_placeholder: str,
) -> rx.Component:
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.hstack(
                    rx.center(
                        rx.icon(icon, size=16),
                        width="2rem",
                        height="2rem",
                        background="#eef2ff",
                        color="#4338ca",
                        border_radius="10px",
                        flex_shrink="0",
                    ),
                    rx.vstack(
                        rx.text(caption, size="1", color="gray", weight="medium", line_height="1", height="0.9rem"),
                        rx.text(
                            rx.cond(name != "", name, placeholder),
                            size="2",
                            weight="medium",
                            color=rx.cond(name != "", "#1c2430", "#98a2b3"),
                            truncate=True,
                            width="100%",
                            line_height="1.2",
                            height="1.2rem",
                        ),
                        rx.text(
                            rx.cond(item_id != "", item_id, "\u00a0"),
                            size="1",
                            color=rx.cond(item_id != "", "gray", "transparent"),
                            truncate=True,
                            width="100%",
                            line_height="1",
                            height="0.9rem",
                        ),
                        spacing="0",
                        align="start",
                        min_width="0",
                        flex="1",
                        height="3rem",
                        justify="center",
                    ),
                    rx.icon("chevron-down", size=16, color="#98a2b3"),
                    width="100%",
                    align="center",
                    spacing="2",
                ),
                variant="surface",
                width="100%",
                height="4.25rem",
                min_height="4.25rem",
                max_height="4.25rem",
                overflow="hidden",
                white_space="normal",
                padding="0.45rem 0.55rem",
                justify="start",
                style={"boxShadow": "0 1px 2px rgba(16, 24, 40, 0.06)"},
            ),
        ),
        rx.popover.content(
            rx.vstack(
                rx.input(
                    rx.input.slot(rx.icon("search", size=16)),
                    placeholder=search_placeholder,
                    value=query,
                    on_change=on_query,
                    width="100%",
                    size="2",
                ),
                rx.box(
                    rx.cond(
                        options.length() > 0,
                        rx.vstack(
                            rx.foreach(options, lambda item: _picker_option(item, selected, on_pick)),
                            spacing="1",
                            width="100%",
                        ),
                        rx.text("Nothing matches.", size="2", color="gray"),
                    ),
                    width="100%",
                    max_height="18rem",
                    overflow_y="auto",
                ),
                spacing="2",
                width="100%",
                align="start",
            ),
            side="right",
            align="start",
            side_offset=8,
            width="24rem",
        ),
        open=is_open,
        on_open_change=on_open,
    )


def data_grid(columns: list[str], rows, empty: str = "Nothing to show.") -> rx.Component:
    return rx.cond(
        rows.length() > 0,
        rx.data_table(
            data=rows,
            columns=columns,
            pagination=True,
            search=True,
            sort=True,
            width="100%",
        ),
        rx.callout(empty, color_scheme="gray", width="100%"),
    )


def copy_block(title: str, value) -> rx.Component:
    return rx.cond(
        value != "",
        rx.vstack(
            rx.hstack(
                rx.text(title, size="2", weight="bold"),
                rx.button("Copy", size="1", variant="soft", on_click=rx.set_clipboard(value)),
                justify="between",
                width="100%",
            ),
            rx.text_area(value=value, read_only=True, width="100%", rows="4"),
            spacing="2",
            width="100%",
            align="start",
        ),
    )


def pre_block(title: str, value) -> rx.Component:
    return rx.cond(
        value != "",
        rx.vstack(
            rx.text(title, size="2", weight="bold"),
            rx.text(value, white_space="pre-wrap", size="2"),
            spacing="2",
            width="100%",
            align="start",
        ),
    )


def json_block(value) -> rx.Component:
    return rx.cond(
        value != "",
        rx.code_block(value, language="json", width="100%", wrap_long_lines=True),
    )


def _timed_callout(color, clearer) -> rx.Component:
    """Remount on every notice so the dismiss timer starts when the toast appears."""
    def branch() -> rx.Component:
        return rx.box(
            rx.callout(AppState.notice, color_scheme=color, width="100%"),
            on_mount=clearer,
            width="100%",
        )

    return rx.cond(AppState.notice_token % 2 == 0, branch(), branch())


def notice_toasts() -> rx.Component:
    info_color = rx.cond(AppState.notice_level == "success", "green", "blue")
    return rx.fragment(
        rx.cond(
            (AppState.notice != "") & (AppState.notice_level == "error"),
            rx.box(
                _timed_callout("red", AppState.schedule_clear_critical),
                position="fixed",
                top="1.25rem",
                left="calc(19rem + (100vw - 19rem) / 2)",
                transform="translateX(-50%)",
                z_index="70",
                width="min(36rem, calc(100vw - 22rem))",
                style={"pointerEvents": "none"},
            ),
        ),
        rx.box(
            rx.cond(
                AppState.busy,
                rx.callout(AppState.busy_message, color_scheme="blue", width="100%"),
            ),
            rx.cond(
                (AppState.notice != "") & (AppState.notice_level == "warning"),
                _timed_callout("orange", AppState.schedule_clear_warning),
            ),
            rx.cond(
                (AppState.notice != "")
                & ((AppState.notice_level == "info") | (AppState.notice_level == "success")),
                _timed_callout(info_color, AppState.schedule_clear_info),
            ),
            position="fixed",
            bottom="1.5rem",
            left="calc(19rem + (100vw - 19rem) / 2)",
            transform="translateX(-50%)",
            z_index="45",
            width="min(36rem, calc(100vw - 22rem))",
            style={"pointerEvents": "none"},
        ),
    )


def _nav_button(label: str, page_id: str) -> rx.Component:
    active = AppState.current_page == page_id
    return rx.button(
        label,
        on_click=AppState.show_page(page_id),
        variant=rx.cond(active, "solid", "ghost"),
        width="100%",
        max_width="100%",
        min_width="0",
        justify="start",
        size="2",
        white_space="normal",
        height="auto",
        text_align="left",
        box_sizing="border-box",
        style={"marginLeft": "0", "marginRight": "0"},
    )


def sidebar() -> rx.Component:
    return rx.box(
        rx.box(
            rx.vstack(
                rx.heading("PSD2 Simulator", size="5"),
                rx.separator(),
                rx.text("Context", weight="bold", size="2"),
                context_picker(
                    "TPP",
                    "building-2",
                    "Select TPP",
                    AppState.selected_client_name,
                    AppState.selected_client_id,
                    AppState.client_query,
                    AppState.set_client_query,
                    AppState.filtered_client_options,
                    AppState.selected_client_label,
                    AppState.select_client,
                    AppState.client_picker_open,
                    AppState.set_client_picker_open,
                    "Search TPP",
                ),
                context_picker(
                    "User",
                    "user-round",
                    "Select user",
                    AppState.selected_user_name,
                    AppState.selected_user_id,
                    AppState.user_query,
                    AppState.set_user_query,
                    AppState.filtered_user_options,
                    AppState.selected_user_label,
                    AppState.select_user,
                    AppState.user_picker_open,
                    AppState.set_user_picker_open,
                    "Search user",
                ),
                rx.separator(),
                rx.text("Navigation", weight="bold", size="2"),
                rx.vstack(
                    *[_nav_button(label, page_id) for label, page_id in NAV_ITEMS],
                    spacing="1",
                    width="100%",
                    min_width="0",
                ),
                rx.separator(),
                rx.text("Tools", weight="bold", size="2"),
                rx.vstack(
                    _nav_button("Kibana Log Miner", "kibana-miner"),
                    _nav_button("Datasheets", "datasheets"),
                    spacing="1",
                    width="100%",
                    min_width="0",
                ),
                spacing="3",
                width="100%",
                min_width="0",
                align="start",
            ),
            flex="1",
            min_height="0",
            min_width="0",
            overflow_x="hidden",
            overflow_y="auto",
            width="100%",
        ),
        rx.box(
            context_picker(
                "Environment",
                "layers",
                "Select environment",
                AppState.current_environment,
                "",
                AppState.environment_query,
                AppState.set_environment_query,
                AppState.filtered_environment_options,
                AppState.current_environment,
                AppState.switch_environment,
                AppState.environment_picker_open,
                AppState.set_environment_picker_open,
                "Search environment",
            ),
            width="100%",
            padding_top="0.75rem",
            margin_top="0.75rem",
            border_top="1px solid #e4e7ec",
            flex_shrink="0",
        ),
        width="19rem",
        min_width="19rem",
        height="100vh",
        padding="1rem",
        background="#f3f5f8",
        border_right="1px solid #e4e7ec",
        display="flex",
        flex_direction="column",
        overflow="hidden",
    )


def page_shell(title: str, *children, header_action=None, fill: bool = False) -> rx.Component:
    header = rx.hstack(
        rx.heading(title, size="7"),
        rx.spacer(),
        header_action or rx.fragment(),
        width="100%",
        align="center",
    )
    body = rx.box(
        *children,
        flex="1",
        min_height="0",
        width="100%",
        overflow="hidden",
        display="flex",
        flex_direction="column",
    ) if fill else rx.fragment(*children)
    return rx.vstack(
        header,
        rx.separator(),
        body,
        spacing="4",
        width="100%",
        height="100%" if fill else "auto",
        min_height="0" if fill else "auto",
        overflow="hidden" if fill else "visible",
        align="start",
    )


def kibana_trace_panel() -> rx.Component:
    return rx.cond(
        AppState.kibana_trace_open,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.heading("Kibana logs", size="4"),
                    rx.badge(AppState.kibana_trace_logs.length()),
                    rx.spacer(),
                    rx.button("Close", size="1", variant="ghost", on_click=AppState.close_kibana_trace),
                    width="100%",
                    align="center",
                ),
                rx.cond(
                    AppState.kibana_trace_span != "",
                    rx.text("X-B3-SpanId ", AppState.kibana_trace_span, size="1", color="gray"),
                ),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(
                            AppState.kibana_trace_logs,
                            lambda item: rx.box(
                                rx.hstack(
                                    rx.cond(
                                        item["component"] != "",
                                        rx.badge(item["component"], variant="soft", size="1"),
                                    ),
                                    rx.text(item["timestamp"], size="1", color="gray"),
                                    spacing="2",
                                    align="center",
                                ),
                                rx.text(item["preview"], size="1"),
                                on_click=AppState.show_kibana_trace_log(item["index"]),
                                width="100%",
                                padding="0.45rem 0.5rem",
                                border_radius="8px",
                                cursor="pointer",
                                background=rx.cond(
                                    AppState.kibana_trace_index == item["index"],
                                    "#eef2ff",
                                    "transparent",
                                ),
                                _hover={"background": "#f4f6fb"},
                            ),
                        ),
                        spacing="1",
                        width="100%",
                        align="start",
                    ),
                    max_height="16rem",
                    width="100%",
                ),
                rx.text_area(
                    value=AppState.kibana_trace_detail,
                    read_only=True,
                    width="100%",
                    rows="14",
                ),
                spacing="2",
                width="100%",
                align="start",
            ),
            position="fixed",
            top="5rem",
            left="50%",
            transform="translateX(-50%)",
            width="min(46rem, calc(100vw - 2.5rem))",
            max_height="calc(100vh - 6.5rem)",
            overflow_y="auto",
            background="white",
            border="1px solid #e4e7ec",
            border_radius="12px",
            box_shadow="0 16px 40px rgba(16, 24, 40, 0.16)",
            padding="1rem",
            z_index="50",
        ),
    )


def kibana_trace_spinner() -> rx.Component:
    return rx.cond(
        AppState.kibana_trace_loading,
        rx.box(
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Loading Kibana logs...", size="3", weight="medium", color="#1c2430"),
                    rx.cond(
                        AppState.kibana_trace_step != "",
                        rx.text(
                            AppState.kibana_trace_step,
                            size="1",
                            color="#667085",
                            text_align="center",
                            width="min(36rem, calc(100vw - 3rem))",
                        ),
                    ),
                    spacing="3",
                    align="center",
                ),
                width="100%",
                height="100%",
            ),
            position="fixed",
            inset="0",
            z_index="60",
            style={
                "background": "radial-gradient(circle at 50% 46%, rgba(79, 70, 229, 0.14), rgba(243, 245, 248, 0.94) 46%)",
                "backdropFilter": "blur(12px)",
            },
        ),
    )


def log_panel() -> rx.Component:
    return rx.fragment(
        kibana_trace_spinner(),
        kibana_trace_panel(),
        rx.cond(
            AppState.current_page != "accounts",
            rx.box(
                rx.button(
                    rx.icon("scroll-text", size=18),
                    on_click=AppState.toggle_log,
                    position="fixed",
                    bottom="1.25rem",
                    right="1.25rem",
                    z_index="40",
                    size="3",
                    variant="solid",
                    border_radius="999px",
                    width="3rem",
                    height="3rem",
                    padding="0",
                ),
                rx.cond(
                    AppState.account_logs.length() > 0,
                    rx.badge(
                        AppState.account_logs.length(),
                        position="fixed",
                        bottom="3.4rem",
                        right="1.1rem",
                        z_index="41",
                        color_scheme="red",
                        variant="solid",
                    ),
                ),
            ),
        ),
        rx.cond(
            AppState.log_open,
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Log", size="4"),
                        rx.button("Clear", size="1", variant="soft", on_click=AppState.clear_account_logs),
                        rx.button("Close", size="1", variant="ghost", on_click=AppState.toggle_log),
                        justify="between",
                        width="100%",
                    ),
                    rx.cond(
                        AppState.account_logs.length() > 0,
                        rx.foreach(
                            AppState.account_logs,
                            lambda log: rx.callout(
                                rx.vstack(
                                    rx.text(log["timestamp"], "  ", log["message"], size="1"),
                                    rx.cond(
                                        log["kibana_url"] != "",
                                        rx.tooltip(
                                            rx.button(
                                                "Kibana",
                                                size="1",
                                                variant="soft",
                                                on_click=AppState.open_kibana_trace(log["request_id"]),
                                            ),
                                            content="Download the X-B3-SpanId logs into the app",
                                        ),
                                    ),
                                    spacing="1",
                                    align="start",
                                    width="100%",
                                ),
                                color_scheme=log["color"],
                                width="100%",
                            ),
                        ),
                        rx.text("No log entries yet.", size="2", color="gray"),
                    ),
                    rx.cond(
                        AppState.refresh_error != "",
                        rx.text_area(value=AppState.refresh_error, read_only=True, width="100%", rows="8"),
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),
                position="fixed",
                bottom="4.75rem",
                right="1.25rem",
                width="26rem",
                max_height="70vh",
                overflow_y="auto",
                background="white",
                border="1px solid #e4e7ec",
                border_radius="12px",
                box_shadow="0 16px 40px rgba(16, 24, 40, 0.16)",
                padding="1rem",
                z_index="40",
            ),
        ),
    )
