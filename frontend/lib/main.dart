import 'package:flutter/material.dart';

import 'core/theme.dart';
import 'features/chat/data/ask_repository.dart';
import 'features/chat/presentation/chat_screen.dart';

void main() {
  runApp(const CompanyBrainApp());
}

/// Root of the Al Dente Company Brain chat application.
class CompanyBrainApp extends StatelessWidget {
  const CompanyBrainApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Al Dente - Company Brain',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.light,
      home: const ChatScreen(repository: AskRepository()),
    );
  }
}
