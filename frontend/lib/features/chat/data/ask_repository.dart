import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/ask_result.dart';

/// Thrown when the backend cannot be reached or returns an unexpected payload.
class AskException implements Exception {
  const AskException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Talks to the backend `POST /ask` endpoint.
///
/// The base URL can be overridden at build time with
/// `--dart-define=API_BASE=http://localhost:8000` (useful for `flutter run`).
/// When empty (the default) requests are resolved relative to the page origin,
/// which is the case when the web build is served by the FastAPI backend.
class AskRepository {
  const AskRepository({this.client, this.apiBase = _envBase});

  static const String _envBase = String.fromEnvironment('API_BASE');

  final http.Client? client;
  final String apiBase;

  Uri get _endpoint =>
      apiBase.isEmpty ? Uri.base.resolve('ask') : Uri.parse('$apiBase/ask');

  Future<AskResult> ask(String question) async {
    final http.Client c = client ?? http.Client();
    try {
      final response = await c
          .post(
            _endpoint,
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'question': question}),
          )
          .timeout(const Duration(seconds: 35));

      if (response.statusCode != 200) {
        throw AskException('Server returned ${response.statusCode}.');
      }
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) {
        throw const AskException('Unexpected response shape.');
      }
      return AskResult.fromJson(decoded);
    } on AskException {
      rethrow;
    } catch (e) {
      throw AskException('Could not reach the Company Brain: $e');
    } finally {
      if (client == null) c.close();
    }
  }
}
