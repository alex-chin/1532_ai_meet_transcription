from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pydub import AudioSegment
import whisper
import tempfile
#pip install pyqt5 pydub openai-whisper
# Инициализация модели Whisper
model = whisper.load_model("base")


class TranscriptionThread(QThread):
    progress_signal = pyqtSignal(int)  # Сигнал для прогресса
    text_signal = pyqtSignal(str)     # Сигнал для текста
    error_signal = pyqtSignal(str)    # Сигнал для ошибок

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path
        self._running = True  # Флаг для остановки

    def run(self):
        try:
            # Конвертация в WAV, если это необходимо
            if not self.audio_path.endswith(".wav"):
                audio = AudioSegment.from_file(self.audio_path)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                audio.export(temp_file.name, format="wav")
                audio_path = temp_file.name
            else:
                audio_path = self.audio_path

            # Разбиение аудио на фрагменты по минуте
            audio = AudioSegment.from_file(audio_path)
            chunks = [audio[i * 60 * 1000:(i + 1) * 60 * 1000] for i in range(len(audio) // (60 * 1000) + 1)]

            # Транскрибация по частям
            full_text = ""
            for i, chunk in enumerate(chunks):
                if not self._running:  # Проверка флага остановки
                    return
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_chunk:
                    chunk.export(temp_chunk.name, format="wav")
                    result = model.transcribe(temp_chunk.name, language="ru")
                    full_text += result['text'] + "\n"
                    self.progress_signal.emit(i + 1)  # Обновляем прогресс

            if self._running:  # Передаем текст только если поток не остановлен
                self.text_signal.emit(full_text)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        """Останавливает выполнение потока."""
        self._running = False


class AudioTranscriberApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Аудио Транскрибация (Whisper)")
        self.resize(400, 300)

        layout = QVBoxLayout()

        self.label = QLabel("Выберите аудиофайл для транскрибации:")

        layout.addWidget(self.label, alignment=Qt.AlignCenter)
        self.label_file = QLabel()
        layout.addWidget(self.label_file, alignment=Qt.AlignCenter)

        self.select_button = QPushButton("Выбрать файл")
        self.select_button.clicked.connect(self.choose_file)
        layout.addWidget(self.select_button, alignment=Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.transcribe_button = QPushButton("Транскрибировать")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        layout.addWidget(self.transcribe_button, alignment=Qt.AlignCenter)

        self.stop_button = QPushButton("Остановить")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_transcription)
        layout.addWidget(self.stop_button, alignment=Qt.AlignCenter)

        self.copy_button = QPushButton("Скопировать")
        self.copy_button.setVisible(False)
        self.copy_button.clicked.connect(self.copy_text)
        layout.addWidget(self.copy_button, alignment=Qt.AlignCenter)

        self.reset_button = QPushButton("Сбросить")
        self.reset_button.setVisible(False)
        self.reset_button.clicked.connect(self.reset_ui)
        layout.addWidget(self.reset_button, alignment=Qt.AlignCenter)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        self.setLayout(layout)

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите аудиофайл", "", "Audio Files (*.wav *.mp3 *.ogg)")
        if file_path:
            self.audio_file_path = file_path
            self.transcribe_button.setEnabled(True)
            self.label_file.setText(file_path)

    def start_transcription(self):
        if hasattr(self, 'audio_file_path') and self.audio_file_path:
            self.text_edit.clear()
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            self.select_button.setVisible(False)
            self.transcribe_button.setVisible(False)
            self.stop_button.setVisible(True)

            self.thread = TranscriptionThread(self.audio_file_path)
            self.thread.progress_signal.connect(self.update_progress)
            self.thread.text_signal.connect(self.display_text)
            self.thread.error_signal.connect(self.show_error)
            self.thread.start()

    def stop_transcription(self):
        """Останавливает транскрибацию."""
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()  # Устанавливаем флаг остановки
            self.thread.quit()
            self.thread.wait()
        self.reset_ui()  # Возвращаем UI в исходное состояние

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_text(self, text):
        """Отображает результат транскрипции."""
        if hasattr(self, 'thread') and not self.thread._running:
            return  # Если поток был остановлен, ничего не делать

        self.progress_bar.setVisible(False)
        self.stop_button.setVisible(False)
        self.copy_button.setVisible(True)
        self.reset_button.setVisible(True)
        self.text_edit.setText(text)
        QMessageBox.information(self, "Успех", "Транскрибация завершена!")

    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "Информация", "Текст скопирован в буфер обмена!")

    def show_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.reset_ui()
        QMessageBox.critical(self, "Ошибка", f"Ошибка транскрибации: {error_message}")

    def reset_ui(self):
        """Сбрасывает UI в начальное состояние."""
        self.text_edit.clear()
        self.stop_button.setVisible(False)
        self.copy_button.setVisible(False)
        self.reset_button.setVisible(False)
        self.select_button.setVisible(True)
        self.select_button.setEnabled(True)
        self.transcribe_button.setVisible(True)
        self.transcribe_button.setEnabled(False)
        self.progress_bar.setVisible(False)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = AudioTranscriberApp()
    window.show()
    sys.exit(app.exec_())
