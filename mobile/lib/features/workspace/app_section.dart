import 'package:flutter/material.dart';

enum AppSection {
  learn('Aprender', Icons.menu_book_outlined, Icons.menu_book),
  practice('Practicar', Icons.back_hand_outlined, Icons.back_hand),
  communicate('Comunicar', Icons.forum_outlined, Icons.forum),
  progress('Progreso', Icons.insights_outlined, Icons.insights),
  profile('Perfil', Icons.person_outline, Icons.person);

  const AppSection(this.label, this.icon, this.selectedIcon);

  final String label;
  final IconData icon;
  final IconData selectedIcon;

  String get description => switch (this) {
    AppSection.learn => 'Materiales de aprendizaje',
    AppSection.practice => 'Actividades para practicar',
    AppSection.communicate => 'Herramientas de comunicación',
    AppSection.progress => 'Tu actividad de aprendizaje',
    AppSection.profile => 'Tu información personal',
  };

  String get emptyMessage => switch (this) {
    AppSection.learn => 'Todavía no hay materiales de aprendizaje disponibles.',
    AppSection.practice =>
      'Todavía no hay actividades de práctica disponibles.',
    AppSection.communicate =>
      'Las herramientas de comunicación todavía no están disponibles.',
    AppSection.progress =>
      'Tu actividad aparecerá aquí cuando empieces a aprender.',
    AppSection.profile =>
      'La información de tu perfil aparecerá aquí cuando esté disponible.',
  };
}
