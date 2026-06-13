import 'package:flutter/material.dart';

import '../data/ask_repository.dart';
import 'chat_view_model.dart';
import 'widgets/message_bubble.dart';

/// Single-page chat interface for the Al Dente Company Brain.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.repository});

  final AskRepository repository;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final ChatViewModel _viewModel = ChatViewModel(widget.repository);
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final FocusNode _focus = FocusNode();

  static const List<String> _suggestions = [
    'How many active GDO customers are there?',
    'Which raw materials does PAS-RIG-500 use?',
    'What is the shelf life and allergens of Rigatoni?',
    'List open complaints from support calls',
  ];

  @override
  void initState() {
    super.initState();
    _viewModel.addListener(_onChange);
  }

  @override
  void dispose() {
    _viewModel.removeListener(_onChange);
    _viewModel.dispose();
    _input.dispose();
    _scroll.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _onChange() {
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _submit([String? value]) {
    final text = value ?? _input.text;
    if (text.trim().isEmpty) return;
    _input.clear();
    _focus.requestFocus();
    _viewModel.send(text);
  }

  @override
  Widget build(BuildContext context) {
    final messages = _viewModel.messages;
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.restaurant_menu, size: 22),
            SizedBox(width: 10),
            Text('Al Dente - Company Brain'),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: messages.isEmpty
                ? _EmptyState(
                    suggestions: _suggestions,
                    onPick: _submit,
                  )
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                    itemCount: messages.length,
                    itemBuilder: (context, index) =>
                        MessageBubble(message: messages[index]),
                  ),
          ),
          _Composer(
            controller: _input,
            focusNode: _focus,
            busy: _viewModel.busy,
            onSubmit: _submit,
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.suggestions, required this.onPick});

  final List<String> suggestions;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.auto_awesome,
                  size: 40, color: theme.colorScheme.primary),
              const SizedBox(height: 16),
              Text('Ask the company brain',
                  style: theme.textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(
                'Customers, orders, production, suppliers, calls, and company '
                'documents - ask anything about Al Dente.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final s in suggestions)
                    ActionChip(
                      label: Text(s),
                      onPressed: () => onPick(s),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.focusNode,
    required this.busy,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool busy;
  final ValueChanged<String> onSubmit;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  focusNode: focusNode,
                  minLines: 1,
                  maxLines: 5,
                  textInputAction: TextInputAction.send,
                  onSubmitted: busy ? null : onSubmit,
                  decoration: const InputDecoration(
                    hintText: 'Ask about customers, orders, specs...',
                  ),
                ),
              ),
              const SizedBox(width: 10),
              FilledButton(
                onPressed: busy ? null : () => onSubmit(controller.text),
                style: FilledButton.styleFrom(
                  shape: const CircleBorder(),
                  padding: const EdgeInsets.all(16),
                ),
                child: busy
                    ? SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: theme.colorScheme.onPrimary,
                        ),
                      )
                    : const Icon(Icons.arrow_upward),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
