###  Helper R Script for Census Data loading
###  This merges the PL data into the shapefile block data and
###  Generates quantiles for the choropleths.
###     
###  NOTE: Since this is run in rpy, the results are visible to python
###  Limit use of values to q_*, sum_TOTPOP, and has_election_data -- others may change


# merge census and supplementary data
contiguityRow<-function(pair) {
	retval <- paste ('        <ContiguityOverride id="',pair[1],'" connect_to="',pair[2],'" />',"\n",sep="")
	return(retval)
}

setwd('/projects/PublicMapping/data')
contiguityOverrideString<-""
if (file.exists("redist_overrides.csv")) {
	exceptions.df<-read.csv("redist_overrides.csv",stringsAsFactors=F,colClasses="character",header=F)
	xsets<-strsplit(exceptions.df[[1]],";")
	ysets<-strsplit(exceptions.df[[2]],";")


	crows<-list()
	for (i in 1:length(xsets)) {
		mergeset <- merge (xsets[[i]],ysets[[i]])
		crows[[i+1]] <- apply(mergeset,1,contiguityRow)
	}

	crows[[1]]<-"<ContiguityOverrides>\n"
	crows[[i+2]]<-"</ContiguityOverrides>\n"
	contiguityOverrideString<-paste(c(crows,recursive=TRUE),sep="",collapse="")
}

cat(contiguityOverrideString,file="/projects/PublicMapping/DistrictBuilder/docs/generated_overrides.xml")

