set datafile separator '\t'
set term pngcairo size 1200,600 enhanced font ",14"
set border lw 1.3 lc rgb "#444444"
set grid back lc rgb "#bbbbbb" lt 1 lw 0.6

array modes[4] = ["no_def","rolling","window","challenge"]
array colors[4] = ["#c0392b","#1f77b4","#ff7f0e","#2ca02c"]
array pts[4] = [7,5,9,13]

# ---------- Legitimate acceptance vs packet loss ----------
set output "figures/p_loss_legit_gnuplot.png"
set xlabel "Packet loss probability"
set ylabel "Legitimate acceptance (%)"
set xrange [0:0.205]
set yrange [78:101]
set key outside top center horizontal samplen 3 spacing 1.2
plot for [idx=1:4] \
    'data/p_loss_legit.tsv' using 1:(column(idx+1)*100) with linespoints \
    lw 2 pt pts[idx] ps 1.3 lc rgb colors[idx] title modes[idx]

# ---------- Replay success vs packet loss ----------
unset logscale y
set output "figures/p_loss_attack_gnuplot.png"
set ylabel "Replay success (%)"
set logscale y
set yrange [1e-3:150]
set key outside bottom center horizontal samplen 3 spacing 1.2
plot for [idx=1:4] \
    'data/p_loss_attack.tsv' using 1:( (column(idx+1)<=0)?1e-3:column(idx+1)*100 ) with linespoints \
    lw 2 pt pts[idx] ps 1.3 lc rgb colors[idx] title modes[idx]
unset logscale y

# ---------- Window trade-off ----------
set output "figures/window_tradeoff_gnuplot.png"
set xlabel "Window size W"
set ylabel "Legitimate acceptance (%)"
set ytics nomirror
set yrange [80:101]
set key left top spacing 1.0
plot \
    'data/window_tradeoff.tsv' using 1:($2*100) with linespoints lc rgb "#ff7f0e" lw 2 pt 9 ps 1.4 title "Legitimate", \
    '' using 1:($3*100) with linespoints lc rgb "#6a51a3" dt 2 lw 2 pt 13 ps 1.4 title "Replay success"

unset output

