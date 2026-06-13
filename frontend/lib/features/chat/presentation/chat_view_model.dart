import 'package:flutter/foundation.dart';

import '../data/ask_repository.dart';
import '../domain/chat_message.dart';

/// Holds the conversation state and orchestrates calls to the backend.
class ChatViewModel extends ChangeNotifier {
  ChatViewModel(this._repository);

  final AskRepository _repository;

  final List<ChatMessage> _messages = <ChatMessage>[];
  bool _busy = false;

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get busy => _busy;

  /// Sends [question] to the backend and appends the user + assistant messages.
  Future<void> send(String question) async {
    final trimmed = question.trim();
    if (trimmed.isEmpty || _busy) return;

    _busy = true;
    _messages
      ..add(ChatMessage.user(trimmed))
      ..add(const ChatMessage.pending());
    final pendingIndex = _messages.length - 1;
    notifyListeners();

    try {
      final result = await _repository.ask(trimmed);
      _messages[pendingIndex] =
          _messages[pendingIndex].copyWith(result: result, pending: false);
    } catch (e) {
      _messages[pendingIndex] =
          _messages[pendingIndex].copyWith(error: e.toString(), pending: false);
    } finally {
      _busy = false;
      notifyListeners();
    }
  }
}
