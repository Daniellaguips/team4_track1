cd /app || { echo T1_STAGE_FAIL=cd; exit 90; }
git apply /sol/gold.diff || { echo T1_STAGE_FAIL=apply_gold; exit 91; }
git apply /sol/tests.diff || { echo T1_STAGE_FAIL=apply_tests; exit 92; }
python -m pytest -q -p no:cacheprovider --color=no tests > /out/pytest.log 2>&1
rc=$?
echo T1_PYTEST_EXIT=$rc
tail -n 3 /out/pytest.log
exit $rc
