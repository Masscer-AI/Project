class ColorPrinter:
    # ANSI escape codes for colors
    COLORS = {
        "reset": "\033[0m",
        "white": "\033[97m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
    }

    def __init__(self):
        pass

    def log(self, *args, **kwargs):
        """Prints text in white (default terminal color)."""
        self._print_with_color(self.COLORS["white"], *args, **kwargs)

    def red(self, *args, **kwargs):
        """Prints text in red."""
        self._print_with_color(self.COLORS["red"], *args, **kwargs)

    def green(self, *args, **kwargs):
        """Prints text in green."""
        self._print_with_color(self.COLORS["green"], *args, **kwargs)

    def yellow(self, *args, **kwargs):
        """Prints text in yellow."""
        self._print_with_color(self.COLORS["yellow"], *args, **kwargs)

    def blue(self, *args, **kwargs):
        """Prints text in blue."""
        self._print_with_color(self.COLORS["blue"], *args, **kwargs)

    def magenta(self, *args, **kwargs):
        """Prints text in magenta."""
        self._print_with_color(self.COLORS["magenta"], *args, **kwargs)

    def cyan(self, *args, **kwargs):
        """Prints text in cyan."""
        self._print_with_color(self.COLORS["cyan"], *args, **kwargs)

    def error(self, *args, **kwargs):
        """Prints a red X followed by the message."""
        self._print_with_color(self.COLORS["red"], "✖", *args, **kwargs)

    def info(self, *args, **kwargs):
        """Prints a blue info icon followed by the message."""
        self._print_with_color(self.COLORS["blue"], "ℹ", *args, **kwargs)

    def success(self, *args, **kwargs):
        """Prints a green check mark followed by the message."""
        self._print_with_color(self.COLORS["green"], "✔", *args, **kwargs)

    def _print_with_color(self, color_code, *args, **kwargs):
        """Helper method to print text with a specific color."""
        print(color_code, end="")
        print(*args, **kwargs)
        print(self.COLORS["reset"], end="")


printer = ColorPrinter()
