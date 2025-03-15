{% extends "layout.html" %}
{% block content %}
  <div class="bg-gray-900/80 rounded-2xl shadow-2xl p-6 backdrop-blur-md border border-cyan-500/30">
    <h1 class="text-4xl font-bold text-orange-400 mb-8 glow">Tuning Details</h1>
    <div class="bg-gray-800/50 rounded-xl p-6 shadow-md">
      <h2 class="text-2xl text-orange-400 mb-4">Plattform: {{ selected_platform }}, Symbol: {{ selected_symbol }}</h2>
      {% if tuning_params %}
        <table class="w-full text-cyan-200">
          <thead>
            <tr class="bg-gray-700">
              <th class="p-2">Parameter</th>
              <th class="p-2">Wert</th>
            </tr>
          </thead>
          <tbody>
            {% for platform, symbols in tuning_params.items() %}
              {% for symbol, params in symbols.items() %}
                {% for key, value in params.items() %}
                  <tr class="hover:bg-gray-600 transition-colors duration-300">
                    <td class="p-2">{{ key }}</td>
                    <td class="p-2">{{ value }}</td>
                  </tr>
                {% endfor %}
              {% endfor %}
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <p class="text-cyan-200">Keine Tuning-Daten vorhanden.</p>
      {% endif %}
      <button onclick="runTuning()" class="bg-orange-700 hover:bg-orange-600 text-white font-bold py-3 px-6 rounded-xl shadow-lg mt-4 transition-transform transform hover:scale-105">Tuning Ausführen</button>
    </div>
  </div>
  <script>
    function runTuning() {
      fetch('/run_tuning', { method: 'POST' }).then(() => location.reload());
    }
  </script>
{% endblock %}