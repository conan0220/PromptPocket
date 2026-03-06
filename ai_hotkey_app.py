import threading
import time
from dataclasses import dataclass
import sys

import keyboard
import pyperclip
import win32con
import win32gui
from openai import OpenAI
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


SYSTEM_PROMPT = """你是一個只輸出最終結果的助手。

你的輸出會被直接貼到使用者目前的輸入框中。
因此你只能輸出可直接貼上的最終內容，不能輸出任何多餘文字。

嚴格禁止輸出以下內容：
- 前言
- 解釋
- 註解
- 結尾
- 客套話
- 標題
- 條列符號
- Markdown 格式 (除非特別註記要寫 Markdown)
- 三引號程式碼區塊
- 「以下是...」
- 「你可以...」
- 「希望這對你有幫助」
- 任何對答案的說明

輸出規則：
- 若要求 powershell，只輸出可直接執行的 powershell 內容。
- 若要求文章，只輸出文章正文。
- 若要求翻譯，只輸出翻譯結果。
- 若要求改寫，只輸出改寫後內容。
- 若要求程式碼，只輸出程式碼本身。
- 若使用者指定格式，嚴格遵守該格式。

如果資訊不足，不要解釋限制，不要反問，不要加說明。
改為輸出最短、最合理、最可直接使用的結果。"""


@dataclass
class AppConfig:
    base_url: str = "http://localhost:8080/v1"
    api_key: str = "EMPTY"
    model: str = "Qwen3.5-9B"
    hotkey: str = "ctrl+space"


class LlmWorker(QObject):
    chunk = Signal(str)
    started = Signal()
    finished = Signal()
    failed = Signal(str)

    def __init__(self, client: OpenAI, model: str, prompt: str):
        super().__init__()
        self._client = client
        self._model = model
        self._prompt = prompt

    @Slot()
    def run(self) -> None:
        self.started.emit()
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._prompt},
                ],
                temperature=0.4,
                top_p=0.9,
                max_tokens=2048,
                stream=True,
            )
            for part in stream:
                if not part.choices:
                    continue
                delta = part.choices[0].delta.content
                if delta:
                    self.chunk.emit(delta)
            self.finished.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class PromptWindow(QMainWindow):
    request_show = Signal()
    request_toggle = Signal()

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.client = OpenAI(base_url=config.base_url, api_key=config.api_key)
        self.worker_thread: QThread | None = None
        self.worker: LlmWorker | None = None
        self.last_foreground_hwnd: int | None = None
        self.is_generating = False

        self.setWindowTitle("Local AI Prompt")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
        )
        self.resize(760, 560)
        self.request_show.connect(self.show_prompt_window)
        self.request_toggle.connect(self.toggle_prompt_window)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "輸入你的需求，例如：我想要知道目前的路徑下有哪些檔案(powershell)"
        )
        self.prompt_input.setFixedHeight(110)
        self.prompt_input.installEventFilter(self)

        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setPlaceholderText("模型輸出會顯示在這裡")

        mono = QFont("Consolas")
        mono.setPointSize(11)
        self.prompt_input.setFont(mono)
        self.output_view.setFont(mono)

        self.status_label = QLabel(
            f"快捷鍵: {self.config.hotkey} | 模型: {self.config.model}"
        )

        self.generate_button = QPushButton("生成 (Enter)")
        self.paste_button = QPushButton("貼上 (Ctrl+Tab)")
        self.close_button = QPushButton("隱藏 (Ctrl+Space)")

        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.paste_button.clicked.connect(self.on_paste_clicked)
        self.close_button.clicked.connect(self.hide)
        self.paste_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.generate_button)
        button_row.addWidget(self.paste_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Prompt"))
        layout.addWidget(self.prompt_input)
        layout.addWidget(QLabel("輸出"))
        layout.addWidget(self.output_view)
        layout.addWidget(self.status_label)
        layout.addLayout(button_row)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.prompt_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Tab and event.modifiers() & Qt.ControlModifier:
                self.on_paste_clicked()
                return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self.on_generate_clicked()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Tab and event.modifiers() & Qt.ControlModifier:
            self.on_paste_clicked()
            return
        super().keyPressEvent(event)

    @Slot()
    def show_prompt_window(self) -> None:
        foreground_hwnd = win32gui.GetForegroundWindow()
        own_hwnd = int(self.winId()) if self.winId() else None
        if foreground_hwnd and foreground_hwnd != own_hwnd:
            self.last_foreground_hwnd = foreground_hwnd
        self.show()
        self.raise_()
        self.activateWindow()
        self.prompt_input.setFocus()
        self.prompt_input.selectAll()

    @Slot()
    def toggle_prompt_window(self) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show_prompt_window()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()

    def on_generate_clicked(self) -> None:
        if self.is_generating:
            return

        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            self.status_label.setText("請先輸入 prompt")
            self.prompt_input.setFocus()
            return

        self.output_view.clear()
        self.paste_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.status_label.setText("生成中...")
        self.is_generating = True

        self.worker_thread = QThread()
        self.worker = LlmWorker(self.client, self.config.model, prompt)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.chunk.connect(self.append_output)
        self.worker.started.connect(self.on_generation_started)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.failed.connect(self.on_generation_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()

    @Slot()
    def on_generation_started(self) -> None:
        self.status_label.setText("模型正在輸出...")

    @Slot(str)
    def append_output(self, text: str) -> None:
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output_view.setTextCursor(cursor)
        self.output_view.ensureCursorVisible()

    @Slot()
    def on_generation_finished(self) -> None:
        self.is_generating = False
        self.generate_button.setEnabled(True)
        has_output = bool(self.output_view.toPlainText().strip())
        self.paste_button.setEnabled(has_output)
        self.status_label.setText("生成完成，可直接貼上")

    @Slot(str)
    def on_generation_failed(self, message: str) -> None:
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.paste_button.setEnabled(False)
        self.status_label.setText("生成失敗")
        QMessageBox.critical(self, "模型呼叫失敗", message)

    @Slot()
    def cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    def on_paste_clicked(self) -> None:
        content = self.output_view.toPlainText()
        if not content.strip():
            self.status_label.setText("目前沒有可貼上的內容")
            return

        pyperclip.copy(content)
        target_hwnd = self.last_foreground_hwnd
        self.hide()
        self.status_label.setText("已複製到剪貼簿")

        if not target_hwnd or not win32gui.IsWindow(target_hwnd):
            return

        def restore_and_paste() -> None:
            try:
                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
                time.sleep(0.12)
                keyboard.press_and_release("ctrl+v")
            except Exception:
                pass

        threading.Thread(target=restore_and_paste, daemon=True).start()


def register_hotkey(window: PromptWindow, hotkey: str) -> None:
    def callback() -> None:
        window.request_toggle.emit()

    keyboard.add_hotkey(hotkey, callback, suppress=False)


def main(config: AppConfig | None = None, show_on_start: bool = True) -> int:
    app = QApplication(sys.argv)
    config = config or AppConfig()
    window = PromptWindow(config)
    register_hotkey(window, config.hotkey)
    if show_on_start:
        window.show_prompt_window()

    app.aboutToQuit.connect(keyboard.unhook_all_hotkeys)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())




