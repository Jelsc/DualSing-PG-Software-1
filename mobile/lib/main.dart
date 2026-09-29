import 'package:flutter/material.dart';

void main() {
  runApp(const DualSignMobileApp());
}

class DualSignMobileApp extends StatelessWidget {
  const DualSignMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DualSign Mobile',
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        appBar: AppBar(title: const Text('DualSign Mobile')),
        body: const Center(child: Text('Mobile shell for Phase 0.')),
      ),
    );
  }
}
