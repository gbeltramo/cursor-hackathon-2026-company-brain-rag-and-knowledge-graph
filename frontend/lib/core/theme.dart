import 'package:flutter/material.dart';

/// Centralized Material 3 theming for the app.
///
/// Light, electric-green look: a vivid green accent on clean neutral surfaces,
/// with uniformly larger typography for readability.
abstract final class AppTheme {
  /// Electric green seed for the color scheme.
  static const Color _seed = Color(0xFF00E676);

  /// A punchier electric green used to override the seed-derived primary so the
  /// accent reads "electric" rather than muted.
  static const Color _electric = Color(0xFF00C853);

  static ThemeData light() => _base(Brightness.light);

  static ThemeData dark() => _base(Brightness.dark);

  static ThemeData _base(Brightness brightness) {
    final isLight = brightness == Brightness.light;
    final scheme = ColorScheme.fromSeed(
      seedColor: _seed,
      brightness: brightness,
    );
    final colorScheme = isLight
        ? scheme.copyWith(
            primary: _electric,
            onPrimary: Colors.white,
            primaryContainer: const Color(0xFFB9F6CA),
            onPrimaryContainer: const Color(0xFF053D1E),
            surface: const Color(0xFFF6FBF7),
          )
        : scheme;

    final base = ThemeData(brightness: brightness);

    return ThemeData(
      colorScheme: colorScheme,
      brightness: brightness,
      useMaterial3: true,
      scaffoldBackgroundColor: colorScheme.surface,
      // Scale all text up uniformly for a larger, more readable UI.
      textTheme: base.textTheme.apply(fontSizeFactor: 1.18, fontSizeDelta: 1),
      appBarTheme: AppBarTheme(
        backgroundColor: colorScheme.surface,
        surfaceTintColor: colorScheme.surfaceTint,
        centerTitle: false,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colorScheme.surfaceContainerHighest,
        hintStyle: TextStyle(
          fontSize: 17,
          color: colorScheme.onSurfaceVariant,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(28),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      ),
    );
  }
}
