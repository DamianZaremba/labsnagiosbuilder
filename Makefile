test:
		flake8 --exclude=migrations,.git \
			--ignore=E501,E225,E121,E123,E124,E125,E127,E128,W404 \
			--exit-zero labsnagiosbuilder || exit 1
		cd labsnagiosbuilder && nosetests
