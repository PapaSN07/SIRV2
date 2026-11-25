/**
 * ECharts réduit aux graphiques utilisés (barres, courbes, secteurs) et au rendu canvas.
 * Chargé à la demande par `provideEchartsCore` (menu Suivi incidents seulement) : rien
 * n'entre dans le bundle initial.
 */
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  AriaComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  AriaComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export default echarts;
