import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_session.dart';
import 'features/auth/auth_screens.dart';
import 'features/workspace/workspace_screen.dart';

class DualSignMobileApp extends StatelessWidget {
  const DualSignMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    const ink = Color(0xFF172B2A);
    const paper = Color(0xFFF6F7F2);
    const leaf = Color(0xFF176B58);

    final colorScheme = ColorScheme.fromSeed(
      seedColor: leaf,
      brightness: Brightness.light,
      surface: paper,
      primary: leaf,
      onPrimary: Colors.white,
      onSurface: ink,
    );

    return MaterialApp(
      title: 'DualSign',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        splashFactory: NoSplash.splashFactory,
        colorScheme: colorScheme,
        scaffoldBackgroundColor: paper,
        appBarTheme: const AppBarTheme(
          backgroundColor: paper,
          foregroundColor: ink,
          surfaceTintColor: Colors.transparent,
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: paper,
          indicatorColor: leaf.withValues(alpha: 0.12),
          labelTextStyle: WidgetStateProperty.resolveWith((states) {
            final selected = states.contains(WidgetState.selected);
            return TextStyle(
              color: selected ? leaf : ink.withValues(alpha: 0.76),
              fontSize: 12,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            );
          }),
        ),
        navigationRailTheme: NavigationRailThemeData(
          backgroundColor: paper,
          indicatorColor: leaf.withValues(alpha: 0.12),
          selectedIconTheme: const IconThemeData(color: leaf),
          unselectedIconTheme: IconThemeData(
            color: ink.withValues(alpha: 0.76),
          ),
        ),
        textTheme: ThemeData.light().textTheme.apply(
          bodyColor: ink,
          displayColor: ink,
        ),
      ),
      home: const _SessionGate(),
    );
  }
}

class _SessionGate extends ConsumerWidget {
  const _SessionGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionBootstrapProvider);
    return session.when(
      loading: () => const SessionStatusScreen(
        title: 'Connecting securely',
        message: 'Checking for a saved DualSign session...',
        icon: Icons.sync,
      ),
      error: (error, _) => AuthScreen(initialError: error.toString()),
      data: (value) => value == null ? const AuthScreen() : const WorkspaceScreen(),
    );
  }
}
