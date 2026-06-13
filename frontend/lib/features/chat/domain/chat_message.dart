import 'ask_result.dart';

/// Who authored a chat message.
enum ChatRole { user, assistant }

/// A single entry in the conversation.
///
/// Assistant messages may be in a [pending] state while awaiting the backend,
/// carry a parsed [result], or hold an [error] string when the request failed.
class ChatMessage {
  const ChatMessage({
    required this.role,
    this.text,
    this.result,
    this.pending = false,
    this.error,
  });

  final ChatRole role;
  final String? text;
  final AskResult? result;
  final bool pending;
  final String? error;

  const ChatMessage.user(this.text)
      : role = ChatRole.user,
        result = null,
        pending = false,
        error = null;

  const ChatMessage.pending()
      : role = ChatRole.assistant,
        text = null,
        result = null,
        pending = true,
        error = null;

  ChatMessage copyWith({AskResult? result, String? error, bool? pending}) {
    return ChatMessage(
      role: role,
      text: text,
      result: result ?? this.result,
      pending: pending ?? this.pending,
      error: error ?? this.error,
    );
  }
}
