BEGIN {
	total = 0;
}
$1 ~ /^maintenance_work_mem/ {
	sub("MB", "", $3);
	total += $3;
}
$1 ~ /^shared_buffers/ {
	sub("MB", "", $3);
	total += $3;
}
END {
	OFMT="%.0f";
	print total * 1024 * 1024;
}